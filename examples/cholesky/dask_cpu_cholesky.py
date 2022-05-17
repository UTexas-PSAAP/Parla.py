import os
import mkl
import argparse
import operator
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import psutil

parser = argparse.ArgumentParser()
parser.add_argument('-workers', type=int, default=1)
parser.add_argument('-perthread', type=int, default=1)
parser.add_argument('-t', type=int, default=1)
parser.add_argument('-process', type=int, default=0)
args = parser.parse_args()

is_process = True if args.process else False

mkl.set_num_threads(args.t)
os.environ["NUMEXPR_NUM_THREADS"] = str(args.t)
os.environ["OMP_NUM_THREADS"] = str(args.t)
os.environ["OPENBLAS_NUM_THREADS"] = str(args.t)
os.environ["VECLIB_MAXIMUM_THREADS"] = str(args.t)

import pprint
from dask.distributed import Client, LocalCluster, get_task_stream, performance_report
from dask.array.core import Array
from dask.array.utils import array_safe, meta_from_array, solve_triangular_safe
from dask.base import tokenize
from dask.highlevelgraph import HighLevelGraph

import dask.array
import dask
import numpy as np
from scipy.linalg.blas import dtrsm
import time

def potrf(a):
    a = np.linalg.cholesky(a)
    return a


def solve(a, b):
    b = b.T
    for i in range(a.shape[0]):
        b[i] /= a[i, i]
        b[i+1:] -= a[i+1:, i:i+1] * b[i:i+1]
    return b.T

def handle_trsm(a, b):
    b = solve_triangular_safe(a, b.T, lower=True)
    return b.T


def gemm(a, b):
    return a@b.T

def syrk(a):
    return a@a.T

def zerofy(a):
    return partial(np.zeros_like, shape=(a.chunks[0][i], a.chunks[1][j]))

def blocked_cholesky(a):
    num_blocks = len(a.chunks[0])
    token = tokenize(a)
    name = "cholesky-" + token
    name_lt_dot = "cholesky-lt-dot-" + token

    dsk = {}
    for i in range(num_blocks):
        if i > 0:
            prevs = []
            for k in range(i):
                prev = name_lt_dot, i, k, i, k
                dsk[prev] = (operator.sub, (a.name, i, i), (syrk, (name, i, k)))
                prevs.append(prev)
            dsk[name, i, i] = (potrf, (sum, prevs))
        else:
            dsk[name, i, i] = (potrf, (a.name, i, i))
        for j in range(i+1, num_blocks):
            if i > 0:
                prevs = []
                for k in range(i):
                    prev = name_lt_dot, j, k, i, k
                    dsk[prev] = (operator.sub, (a.name, j, i), (gemm, (name, j, k), (name, i, k)))
                    prevs.append(prev)
                dsk[name, j, i] = (handle_trsm, (name, i, i), (sum, prevs))
            else:
                dsk[name, j, i] = (handle_trsm, (name, i, i), (a.name, j, i))

    # Zerofy the upper matrix.
    for i in range(num_blocks):
        for j in range(num_blocks):
            if i < j:
                dsk[name, i, j] = (
                     partial(np.zeros_like, shape=(a.chunks[0][i], a.chunks[1][j])),
                     meta_from_array(a),
                )

    graph_lower = HighLevelGraph.from_collections(name, dsk, dependencies=[a])
    a_meta = meta_from_array(a)
    cho = np.linalg.cholesky(array_safe(
        [[1, 2], [2, 5]], dtype=a.dtype, like=a_meta))
    meta = meta_from_array(a, dtype=cho.dtype)

    lower = Array(graph_lower, name, shape=a.shape, chunks=a.chunks, meta=meta)
    #lower.visualize(filenmae='check.svg')
    return lower

if __name__ == '__main__':
    total_threads = int(args.perthread) * int(args.workers)
    pool = ThreadPoolExecutor(args.workers)
    with dask.config.set(pool=pool):
        cluster = LocalCluster(n_workers=args.workers, threads_per_worker=args.perthread, processes=False)
        #print(cluster)
        client = Client(cluster)
        n = 20000
        block_size = 2000
        np.random.seed(10)
        a = np.random.rand(n, n)
        a = a @ a.T
        da = dask.array.from_array(a, chunks=(block_size, block_size))
        print("Cholesky starts")
        chol = blocked_cholesky(da)
        (chol,) = dask.optimize(chol)
        start = time.perf_counter()
        #chol.visualize(filename='cholesky.svg')
        #with performance_report(filename="dask-profile"+str(args.workers)+"-"+str(args.perthread)+".html") as ts:
        chol.compute()
        stop = time.perf_counter()
        print("Memory consumption: ", psutil.Process().memory_info().rss / (1024 * 1024 * 1024))
        print("Time:", stop - start, flush=True)