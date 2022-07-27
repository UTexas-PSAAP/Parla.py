import os
import sys
import argparse
import pexpect as pe
import re



######
# Helper functions
######


def parse_times(output):
    times = []
    for line in output.splitlines():
        line = str(line).strip('\'')
        if "Time" in line:
            times.append(float(line.split()[-1].strip()))
    return times

def parse_nbody_times(output):
    times = []
    for line in output.splitlines():
        line = str(line).strip('\'')
        if "end-to-end     ," in line:
            times.append(float(line.split(",")[-1].strip()))
    return times

def parse_cublas_times(output):
    output = str(output)
    prog = re.findall(r"T:[ ]*\d+\.\d+", output)
    result = prog[-1]
    prog = re.findall(r"\d+\.\d+", result)
    result = prog[-1]
    result = result.strip()
    return result

def parse_synthetic_times(output):
    output = str(output)
    prog = re.findall(r"Graph(.*)\\r\\nParla", output)
    times = []
    for result in prog:
        p = re.findall(r"Median = \d+\.\d+", result)
        r = p[-1]
        p = re.findall(r"\d+\.\d+", r)
        r = p[-1]
        r = r.strip()
        times.append(r)
    if len(times) > 1:
        return times
    return times[0]

def parse_magma_times(output):
    output = str(output)
    prog = re.findall(r"\([ ]*\d+\.\d+\)", output)
    result = prog[-1]
    result = result.strip("()").strip()
    return result


#######
# Define functions to gather each result (per figure, per app)
#######

#Test:
def run_test(gpu_list, timeout):
    output_dict = {}

    #Loop over number of GPUs in each subtest

    print("\t   [Running Test Script 1/1]")
    for n_gpus in gpu_list:
        command = f"python test_script.py -ngpus {n_gpus}"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t    {n_gpus} GPUs: {times}")
        output_dict[n_gpus] = times

    return output_dict

#Figure 10: Cholesky 28K Magma
def run_cholesky_magma(gpu_list, timeout):

    #Put testing directory on PATH
    magma_root = os.environ.get("MAGMA_ROOT")
    if not magma_root:
        raise Exception("MAGMA_ROOT not set")
    os.environ["PATH"] = magma_root+"/testing/"+":"+os.environ.get("PATH")

    output_dict = {}

    print("\t   [Running Cholesky 28K (MAGMA) 1/1]")
    #Loop over number of GPUs in each subtest
    for n_gpus in gpu_list:
        command = f"./testing_dpotrf_mgpu --ngpu {n_gpus} -N 28000"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_magma_times(output)
        print(f"\t    {n_gpus} GPUs: {times}")
        output_dict[n_gpus] = times

    return output_dict

#Figure 10: Cholesky
def run_cholesky_28(gpu_list, timeout):
    output_dict = {}

    sub_dict = {}

    # Generate input file
    if not os.path.exists("examples/cholesky/chol_28000.npy"):

        print("\t  --Making input matrix...")
        command = f"python examples/cholesky/make_cholesky_input.py -n 28000 -output examples/cholesky/chol_28000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        print("\t  --Generated input matrix.")


    print("\t   [Running Cholesky 28K (2Kx2K Blocks) 1/3] Manual Movement, User Placement")
    #Test 1: Manual Movement, User Placement
    for n_gpus in gpu_list:
        command = f"python examples/cholesky/blocked_cholesky_manual.py -ngpus {n_gpus} -fixed 1 -b 2000 -nblocks 14 -matrix examples/cholesky/chol_28000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times

    output_dict["m,u"] = sub_dict

    #Test 2: Automatic Movement, User Placement
    print("\t   [Running Cholesky 28K (2Kx2K Blocks) 2/3] Automatic Movement, User Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/cholesky/blocked_cholesky_automatic.py -ngpus {n_gpus} -fixed 1 -b 2000 -nblocks 14 -matrix examples/cholesky/chol_28000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,u"] = sub_dict

    #Test 3: Automatic Movement, Policy Placement
    print("\t   [Running Cholesky 28K (2Kx2K Blocks) 3/3] Automatic Movement, Policy Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/cholesky/blocked_cholesky_automatic.py -ngpus {n_gpus} -fixed 0 -b 2000 -nblocks 14"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,p"] = sub_dict

    return output_dict

#Figure 13: Parla Cholesky (CPU)
def run_cholesky_20_host(core_list, timeout):
    output_dict = {}

    sub_dict = {}

    # Generate input file
    if not os.path.exists("examples/cholesky/chol_20000.npy"):
        print("\t  --Making input matrix...")
        command = f"python examples/cholesky/make_cholesky_input.py -n 20000 -output examples/cholesky/chol_20000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        print("\t  --Generated input matrix.")

    cpu_cores = [ 1, 2, 4, 8, 16, 32, 52 ]
    print("\t   Running CPU:")
    #Test 1: Manual Movement, User Placement
    for num_cores in cpu_cores:
        command = f"python examples/cholesky/blocked_cholesky_cpu.py -matrix examples/cholesky/chol_20000.npy -b 2000 -workers {num_cores}"
        print(command, "...")
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {num_cores} CPU cores: {times}")
        sub_dict[num_cores] = times
    output_dict["cpu"] = sub_dict
    return output_dict

#Figure 13: Parla Cholesky (GPU)
def run_cholesky_20_gpu(gpu_list, timeout):
    output_dict = {}

    sub_dict = {}

    # Generate input file
    if not os.path.exists("examples/cholesky/chol_20000.npy"):
        print("\t  --Making input matrix...")
        command = f"python examples/cholesky/make_cholesky_input.py -n 20000 -output examples/cholesky/chol_20000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        print("\t  --Generated input matrix.")

    gpu_list = [ 1, 2, 3, 4 ]
    print("\t   Running GPU:")
    #Test 1: Manual Movement, User Placement
    for n_gpus in gpu_list:
        cuda_visible_devices = list(range(n_gpus))
        cuda_visible_devices = ','.join(map(str, cuda_visible_devices))
        print(f"Resetting CUDA_VISIBLE_DEVICES={cuda_visible_devices}")
        os.environ['CUDA_VISIBLE_DEVICES'] = str(cuda_visible_devices)
        command = f"python examples/cholesky/blocked_cholesky_manual.py -matrix examples/cholesky/chol_20000.npy -fix 1 -ngpus {n_gpus}"
        print("Current running:", command)
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["gpu"] = sub_dict
    return output_dict

#Figure 13: Dask Cholesky (CPU)
def run_dask_cholesky_20_host(cores_list, timeout):
    output_dict = {}

    sub_dict = {}

    # Generate input file
    if not os.path.exists("examples/cholesky/chol_20000.npy"):
        print("\t  --Making input matrix...")
        command = f"python examples/cholesky/make_cholesky_input.py -n 20000 -output examples/cholesky/chol_20000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        print("\t  --Generated input matrix.")

    worker_list = [ 1, 2, 4 ]
    # Per-thread per each worker.
    perthread_list = [ [ 1 ], [ 1 ], [ 1, 2, 4 ] ]
    print("\t   Running Dask CPU:")
    #Test 1: Manual Movement, User Placement
    for wi in range(len(worker_list)):
        n_workers = worker_list[wi]
        for pt in perthread_list[wi]:
            command = f"python examples/cholesky/dask/dask_cpu_cholesky.py -workers {n_workers} -perthread {pt} -matrix examples/cholesky/chol_20000.npy"
            print(command, "...")
            output = pe.run(command, timeout=timeout, withexitstatus=True)
            #Make sure no errors or timeout were thrown
            assert(output[1] == 0)
            #Parse output
            times = parse_times(output[0])
            n_threads = n_workers * pt
            print(f"\t\t    {n_threads} CPU cores: {times}")
            sub_dict[n_workers] = times
    output_dict["dask-cpu"] = sub_dict
    return output_dict

#Figure 13: Dask Cholesky (GPU)
def run_dask_cholesky_20_gpu(gpu_list, timeout):
    output_dict = {}

    sub_dict = {}

    # Generate input file
    if not os.path.exists("examples/cholesky/chol_20000.npy"):
        print("\t  --Making input matrix...")
        command = f"python examples/cholesky/make_cholesky_input.py -n 20000 -output examples/cholesky/chol_20000.npy"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        print("\t  --Generated input matrix.")

    gpu_list = [ 1, 2, 3, 4 ]
    print("\t   Running Dask GPU:")
    #Test 1: Manual Movement, User Placement
    for n_gpus in gpu_list:
        cuda_visible_devices = list(range(n_gpus))
        cuda_visible_devices = ','.join(map(str, cuda_visible_devices))
        print(f"Resetting CUDA_VISIBLE_DEVICES={cuda_visible_devices}")
        os.environ['CUDA_VISIBLE_DEVICES'] = str(cuda_visible_devices)
        os.environ['UCX_TLS'] = "cuda,cuda_copy,cuda_ipc,tpc"
        command = f"python examples/cholesky/dask/dask_gpu_cholesky.py -matrix examples/cholesky/chol_20000.npy"
        print("Current running:", command)
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        # DASK-GPU makes an asyncio error after the app completes. so ignore it.
        #assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["dask-gpu"] = sub_dict
    return output_dict


#Figure 10: Jacobi
def run_jacobi(gpu_list, timeout):
    output_dict = {}

    sub_dict = {}

    print("\t   [Running 1/3] Manual Movement, User Placement")
    #Test 1: Manual Movement, User Placement
    for n_gpus in gpu_list:
        command = f"python examples/jacobi/jacobi_manual.py -ngpus {n_gpus} -fixed 1"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times

    output_dict["m,u"] = sub_dict

    #Test 2: Automatic Movement, User Placement
    print("\t   [Running 2/3] Automatic Movement, User Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/jacobi/jacobi_automatic.py -ngpus {n_gpus} -fixed 1"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,u"] = sub_dict

    #Test 3: Automatic Movement, Policy Placement
    print("\t   [Running 3/3] Automatic Movement, Policy Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/jacobi/jacobi_automatic.py -ngpus {n_gpus} -fixed 0"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,p"] = sub_dict

    return output_dict

#Figure 10: Matmul 32K Magma
def run_matmul_cublas(gpu_list, timeout):

    #Put testing directory on PATH
    cublasmg_root = os.environ.get("CUBLASMG_ROOT")
    cudamg_root = os.environ.get("CUDAMG_ROOT")
    if not cublasmg_root:
        raise Exception("CUBLASMG_ROOT not set")
    if not cudamg_root:
        raise Exception("CUDAMG_ROOT not set")

    os.environ["LD_LIBRARY_PATH"] = cudamg_root+"/lib/"+":"+os.environ.get("LD_LIBRARY_PATH")
    os.environ["LD_LIBRARY_PATH"] = cublasmg_root+"/lib/"+":"+os.environ.get("LD_LIBRARY_PATH")
    os.environ["PATH"] = cublasmg_root+"/test/"+":"+os.environ.get("PATH")

    output_dict = {}
    #Loop over number of GPUs in each subtest
    print("\t   [Running Matmul 32K (MAGMA) 1/1]")
    for n_gpus in gpu_list:
        command = f"./{n_gpus}gpuGEMM.exe"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_cublas_times(output)
        print(f"\t    {n_gpus} GPUs: {times}")
        output_dict[n_gpus] = times

    return output_dict

#Figure 10: Matmul
def run_matmul(gpu_list, timeout):

    output_dict = {}

    sub_dict = {}

    print("\t   [Running 1/3] Manual Movement, User Placement")
    #Test 1: Manual Movement, User Placement
    for n_gpus in gpu_list:
        command = f"python examples/matmul/matmul_manual.py -ngpus {n_gpus} -fixed 1 -n 32000"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times

    output_dict["m,u"] = sub_dict

    #Test 2: Automatic Movement, User Placement
    print("\t   [Running 2/3] Automatic Movement, User Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/matmul/matmul_automatic.py -ngpus {n_gpus} -fixed 1 -n 32000"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,u"] = sub_dict

    #Test 3: Automatic Movement, Policy Placement
    print("\t   [Running 3/3] Automatic Movement, Policy Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/matmul/matmul_automatic.py -ngpus {n_gpus} -fixed 0 -n 32000"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,p"] = sub_dict

    return output_dict

#Figure 10: BLR
def run_blr(gpu_list):
    pass

#Figure 10: NBody
def run_nbody(gpu_list, timeout):
    output_dict = {}

    # Generate input file
    if not os.path.exists("examples/nbody/python-bh/input/n10M.txt"):
        command = f"python examples/nbody/python-bh/bin/gen_input.py normal 10000000 examples/nbody/python-bh/input/n10M.txt"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)

    # Test 1: Manual Movement, User Placement
    print("\t   [Running 1/3] Manual Movement, User Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/nbody/python-bh/bin/run_2d.py examples/nbody/python-bh/input/n10M.txt 1 1 examples/nbody/python-bh/configs/parla{n_gpus}_eager_sched.ini"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_nbody_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times

        output_dict["m,u"] = sub_dict

    # Test 2: Automatic Movement, User Placement
    print("\t   [Running 2/3] Automatic Movement, User Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/nbody/python-bh/bin/run_2d.py examples/nbody/python-bh/input/n10M.txt 1 1 examples/nbody/python-bh/configs/parla{n_gpus}_eager.ini"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_nbody_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,u"] = sub_dict

    # Test 3: Automatic Movement, Policy Placement
    print("\t   [Running 3/3] Automatic Movement, Policy Placement")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/nbody/python-bh/bin/run_2d.py examples/nbody/python-bh/input/n10M.txt 1 1 examples/nbody/python-bh/configs/parla{n_gpus}.ini"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_nbody_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    output_dict["a,p"] = sub_dict

    return output_dict

#Figure 10: Synthetic Reduction
def run_reduction(gpu_list):
    pass

#Figure 10: Synthetic Independent
def run_independent(gpu_list):
    pass

#Figure 10: Synthetic Serial
def run_serial():
    pass

#Figure 15: Batched Cholesky Variants
def run_batched_cholesky(gpu_list, timeout):
    cpu_dict = {}

    print("\t   [Running 1/2] CPU Support")
    sub_dict = {}
    l = [0].extent(gpu_list)
    for n_gpus in l:
        command = f"python examples/variants/batched_cholesy.py -ngpus {n_gpus} -use_cpu 1"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    cpu_dict[1] = sub_dict

    print("\t   [Running 2/2] GPU Only")
    sub_dict = {}
    for n_gpus in gpu_list:
        command = f"python examples/variants/batched_cholesy.py -ngpus {n_gpus} -use_cpu 0"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_times(output[0])
        print(f"\t\t    {n_gpus} GPUs: {times}")
        sub_dict[n_gpus] = times
    cpu_dict[0] = sub_dict

    return cpu_dict


#Figure 12: Prefetching Plot
def run_prefetching_test(gpu_list, timeout):
    auto_dict = {}
    data_sizes = [2, 4, 40]
    data_map = ["32MB", "64MB", "640MB"]
    sub_dict = {}
    idx = 0
    print("\t   [Running 1/2] Manual Movement")
    for data_size in data_sizes:
        command = f"python examples/synthetic/run.py -graph examples/synthetic/artifact/graphs/prefetch.gph -data_move 1 -loop 5 -d {data_size}"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_synthetic_times(output[0])
        print(f"\t {data_map[idx]} Data: {times}")
        sub_dict[data_size] = times
        idx += 1
    auto_dict["m"] = sub_dict

    sub_dict = {}
    idx = 0
    print("\t   [Running 2/2] Automatic Movement")
    for data_size in data_sizes:
        command = f"python examples/synthetic/run.py -graph examples/synthetic/artifact/graphs/prefetch.gph -data_move 2 -loop 5 -d {data_size}"
        output = pe.run(command, timeout=timeout, withexitstatus=True)
        #Make sure no errors or timeout were thrown
        assert(output[1] == 0)
        #Parse output
        times = parse_synthetic_times(output[0])
        print(f"\t {data_map[idx]} Data: {times}")
        sub_dict[data_size] = times
        idx += 1
    auto_dict["a"] = sub_dict

    return auto_dict

#Figure 14: Independent Parla Scaling
def run_independent_parla_scaling(thread_list, timeout):
    n = 1000
    #sizes = [800, 1600, 3200, 6400, 12800, 25600, 51200, 102400]
    sizes = [800, 1600]
    size_dict = {}
    for size in sizes:
        thread_dict = {}
        for thread in thread_list:
            command = "python examples/synthetic/run.py -graph examples/synthetic/artifact/graphs/independent_1000.gph -threads ${threads} -data_move 0 -weight ${size} -n ${n}"
            output = pe.run(command, timeout=timeout, withexitstatus=True)
            #Make sure no errors or timeout were thrown
            assert(output[1] == 0)
            #Parse output
            times = parse_synthetic_times(output[0])
            print(f"\t{size} ms: {thread} threads: {times}")
            thread_dict[thread] = times
        size_dict[size] = thread_dict
    return size_dict

#Figure 14: Independnet Dask Scaling
def run_independent_dask_thread_scaling(thread_list, timeout):
    n = 1000
    #sizes = [800, 1600, 3200, 6400, 12800, 25600, 51200, 102400]
    sizes = [800, 1600]
    size_dict = {}
    for size in sizes:
        thread_dict = {}
        for thread in thread_list:
            command = "python examples/synthetic/artifact/scripts/run_dask_thread.py -workers ${threads} -size ${size} -n ${n}"
            output = pe.run(command, timeout=timeout, withexitstatus=True)
            #Make sure no errors or timeout were thrown
            assert(output[1] == 0)
            #Parse output
            times = parse_synthetic_times(output[0])
            print(f"\t{size} ms: {thread} threads: {times}")
            thread_dict[thread] = times
        size_dict[size] = thread_dict
    return size_dict

#Figure 14: Independnet Dask Scaling
def run_independent_dask_process_scaling(thread_list, timeout):
    n = 1000
    #sizes = [800, 1600, 3200, 6400, 12800, 25600, 51200, 102400]
    sizes = [800, 1600]
    size_dict = {}
    for size in sizes:
        thread_dict = {}
        for thread in thread_list:
            command = "python examples/synthetic/artifact/scripts/run_dask_process.py -workers ${threads} -size ${size} -n ${n}"
            output = pe.run(command, timeout=timeout, withexitstatus=True)
            #Make sure no errors or timeout were thrown
            assert(output[1] == 0)
            #Parse output
            times = parse_synthetic_times(output[0])
            print(f"\t{size} ms: {thread} threads: {times}")
            thread_dict[thread] = times
        size_dict[size] = thread_dict
    return size_dict

#Figure 14: GIL test
def run_GIL_test():
    pass

test = [run_cholesky_28]
figure_10 = [run_jacobi, run_matmul, run_blr, run_nbody, run_reduction, run_independent, run_serial]
figure_13 = [run_cholesky_20_host, run_cholesky_20_gpu, run_dask_cholesky_20_host, run_dask_cholesky_20_gpu]
#figure_13 = [run_dask_cholesky_20_host, run_dask_cholesky_20_gpu]
#figure_13 = [run_cholesky_20_host]
figure_15 = [run_batched_cholesky]
figure_12 = [run_prefetching_test]

figure_dictionary = {}
figure_dictionary['Figure_10'] = figure_10
figure_dictionary['Figure_13'] = figure_13
figure_dictionary['Figure_15'] = figure_15
figure_dictionary['Figure_12'] = figure_12
figure_dictionary['Figure_test'] = test

figure_output = {}

if __name__ == '__main__':
    import os
    import sys
    parser = argparse.ArgumentParser(description='Runs the benchmarks')
    parser.add_argument('--figures', type=int, nargs="+", help='Figure numbers to generate', default=None)
    parser.add_argument('--timeout', type=int, help='Max Timeout for a benchmark', default=1000)

    args = parser.parse_args()

    cuda_visible_devices = os.environ.get('CUDA_VISIBLE_DEVICES')
    if cuda_visible_devices is None:
        print("Warning CUDA_VISIBLE_DEVICES is not set.")
        cuda_visible_devices = list(range(4))
        cuda_visible_devices = ','.join(map(str, cuda_visible_devices))
        print(f"Setting CUDA_VISIBLE_DEVICES={cuda_visible_devices}")
        os.environ['CUDA_VISIBLE_DEVICES'] = str(cuda_visible_devices)

    ngpus = [1, 2, 4]


    if args.figures is None:
        figure_list = ["-1"]
    else:
        figure_list = args.figures

    for figure_num in figure_list:
        if int(figure_num) < 0:
            figure_num = "test"
        figure = f"Figure_{figure_num}"
        if figure not in figure_dictionary:
            print(f"Experiments for {figure} not found")
            continue

        total_tests = len(figure_dictionary[figure])
        i = 1
        print("Starting collection for :", figure)
        for test in figure_dictionary[figure]:
            test_output = {}
            print("\t ++Experiment {}/{}. Name: {}".format(i, total_tests, test.__name__))
            output_dict = test(ngpus, args.timeout)
            test_output[test.__name__] = output_dict
            print("\t --Experiment {}/{} Completed. Output: {}".format(i, total_tests, output_dict))
            i += 1
        figure_output[figure] = test_output
        print(f"Collection for {figure} complete")


    print("All experiments complete.")
    print("Output:")
    print(figure_output)







