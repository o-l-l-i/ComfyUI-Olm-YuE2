"""Read-only CUDA memory snapshots; never reset the host's peak counters."""

import torch


def cuda_memory(device):
    device = torch.device(device)
    if device.type != "cuda":
        return None
    free, total = torch.cuda.mem_get_info(device)
    return {"allocator": torch.cuda.get_allocator_backend(),
            "allocated_bytes": torch.cuda.memory_allocated(device),
            "reserved_bytes": torch.cuda.memory_reserved(device),
            "device_used_bytes": total - free}
