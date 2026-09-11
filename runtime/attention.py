"""Adapt YuE2 layouts and masks to ComfyUI's selected attention operation."""

from functools import partial

import torch
from comfy.ldm.modules.attention import optimized_attention_for_device

from .._vendor.yue2.modeling_yue2 import Attention, YuE2ForCausalLM
from .._vendor.yue2.nar import attention as nar_attention


def comfy_sdpa(query, key, value, *, attn_mask=None, is_causal=False, enable_gqa=None):
    if enable_gqa is None:
        enable_gqa = query.shape[1] != key.shape[1]
    if attn_mask is not None and attn_mask.dtype == torch.bool:
        attn_mask = torch.zeros_like(attn_mask, dtype=query.dtype).masked_fill(~attn_mask, float("-inf"))
    if is_causal:
        outputs = []
        # Bound explicit causal masks while preserving absolute query positions.
        for start in range(0, query.shape[-2], 512):
            end = min(start + 512, query.shape[-2])
            used = min(end, key.shape[-2])
            visible = torch.arange(used, device=query.device)[None, :] <= torch.arange(
                start, end, device=query.device)[:, None]
            mask = torch.zeros_like(visible, dtype=query.dtype) if attn_mask is None else attn_mask[..., start:end, :used]
            mask = mask.masked_fill(~visible, float("-inf"))
            outputs.append(comfy_sdpa(query[..., start:end, :], key[..., :used, :],
                                      value[..., :used, :], attn_mask=mask, enable_gqa=enable_gqa))
        return torch.cat(outputs, dim=-2)
    operation = optimized_attention_for_device(query.device, mask=attn_mask is not None)
    return operation(query, key, value, query.shape[1], mask=attn_mask,
                     skip_reshape=True, skip_output_reshape=True,
                     enable_gqa=enable_gqa)


def patch_attention(patcher, model):
    if isinstance(model, YuE2ForCausalLM):
        patcher.add_object_patch("module.nar_attention", partial(nar_attention, sdpa_fn=comfy_sdpa))
        for name, module in model.named_modules():
            if isinstance(module, Attention):
                patcher.add_object_patch(f"module.{name}.sdpa", comfy_sdpa)
