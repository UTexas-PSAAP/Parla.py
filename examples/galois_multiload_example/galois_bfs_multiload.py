from threading import Thread
from parla.multiload import multiload, multiload_contexts, mark_module_as_global

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("input", help="Path to input graph")
parser.add_argument("vecs", help="# of threads/vecs to run", type=int)
args = parser.parse_args()

with multiload():
    import parla_galois.core

from parla_galois.core import py_load_file, py_init_galois
py_init_galois()
g = py_load_file(args.input)

def bfs_sssp(i):
    with multiload_contexts[i]:
        source = i
        report = (i+1)*5
        slot = i
        g = py_load_file(args.input)
        parla_galois.core.py_bfs(g, source, slot)
        print(f"distance from {source} to {report} at slot {slot} is {parla_galois.core.py_distance(g, report, slot)}")

threads = []
for i in range(args.vecs):
    multiload_contexts[i].load_stub_library("numa")
    #bfs_sssp(i)
    threads.append(Thread(target=bfs_sssp, args=(i,)))

for t in threads: t.start()
for t in threads: t.join()