# Two-node NCCL all-reduce sweep: latency at decode-sized messages, bandwidth at large ones.
# Env: RANK, MASTER (bootstrap IP), PORT. Prints one RESULT line per size from rank 0.
import os, time, torch, torch.distributed as dist

rank = int(os.environ["RANK"])
torch.cuda.set_device(0)
dist.init_process_group("nccl", init_method=f"tcp://{os.environ['MASTER']}:{os.environ['PORT']}",
                        rank=rank, world_size=2, device_id=torch.device("cuda:0"))

sizes = [4 << 10, 64 << 10, 256 << 10, 1 << 20, 4 << 20, 16 << 20, 64 << 20, 256 << 20, 512 << 20]
for nbytes in sizes:
    x = torch.ones(nbytes // 2, dtype=torch.bfloat16, device="cuda")
    iters = 200 if nbytes <= (1 << 20) else 50 if nbytes <= (16 << 20) else 10
    for _ in range(5):
        dist.all_reduce(x)
    torch.cuda.synchronize()
    dist.barrier()
    t = time.perf_counter()
    for _ in range(iters):
        dist.all_reduce(x)
    torch.cuda.synchronize()
    dt = (time.perf_counter() - t) / iters
    # 2 ranks: busbw = algbw * 2(n-1)/n = algbw
    if rank == 0:
        print(f"RESULT size={nbytes} lat_us={dt * 1e6:.1f} busbw_GBps={nbytes / dt / 1e9:.2f}", flush=True)
    del x
dist.destroy_process_group()
