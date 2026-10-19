# Two-node NCCL all-reduce soak: one message size, repeated for about SOAK seconds.
# Env: RANK, MASTER (bootstrap IP), PORT, SOAK (s), SIZE (bytes). Prints one RESULT line from rank 0.
import os, time, torch, torch.distributed as dist

rank = int(os.environ["RANK"])
soak = float(os.environ.get("SOAK", "180")); nbytes = int(os.environ.get("SIZE", str(256 << 20)))
torch.cuda.set_device(0)
dist.init_process_group("nccl", init_method=f"tcp://{os.environ['MASTER']}:{os.environ['PORT']}",
                        rank=rank, world_size=2, device_id=torch.device("cuda:0"))
x = torch.ones(nbytes // 2, dtype=torch.bfloat16, device="cuda")
for _ in range(5):
    dist.all_reduce(x)
torch.cuda.synchronize()
# both ranks must run the same number of all-reduces: time 20 on rank 0, then share the count
t = time.perf_counter()
for _ in range(20):
    dist.all_reduce(x)
torch.cuda.synchronize()
n = torch.tensor([int(soak / ((time.perf_counter() - t) / 20)) if rank == 0 else 0], device="cuda")
dist.broadcast(n, 0)
iters = int(n.item())
dist.barrier()
t = time.perf_counter()
for _ in range(iters):
    dist.all_reduce(x)
torch.cuda.synchronize()
dt = time.perf_counter() - t
# 2 ranks: busbw = algbw * 2(n-1)/n = algbw
if rank == 0:
    v = torch.cuda.nccl.version()
    print(f"RESULT nccl={'.'.join(map(str, v)) if isinstance(v, tuple) else v} torch={torch.__version__} "
          f"size={nbytes} iters={iters} secs={dt:.1f} busbw_GBps={nbytes * iters / dt / 1e9:.2f}", flush=True)
dist.destroy_process_group()
