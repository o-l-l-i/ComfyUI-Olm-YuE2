"""Whole-model and optional synthesis-group residency through ComfyUI."""

from contextlib import contextmanager, ExitStack
import logging

import torch
from comfy import model_management
from comfy.model_patcher import ModelPatcher


class _ModelContainer(torch.nn.Module):
    def __init__(self, module):
        super().__init__()
        self.module = module
        # Transformers exposes a read-only device property; the patcher owns this one.
        self.device = torch.device("cpu")

    def get_dtype(self):
        return next(self.module.parameters()).dtype


class YuE2TokenLayers(_ModelContainer):
    pass


class YuE2AcousticLayers(_ModelContainer):
    pass


def synthesis_groups(model):
    ar = [model.model.embed_tokens, model.lm_head]
    acoustic = [model.model.norm, model.model.rotary_emb, model.vae2llm,
                model.llm2vae, model.time_embedder, model.latent_pos_embed]
    for layer in model.model.layers:
        ar.extend((layer.input_layernorm, layer.self_attn, layer.post_attention_layernorm, layer.mlp))
        acoustic.extend((layer.nar_input_layernorm, layer.nar_self_attn,
                         layer.nar_pre_mlp_layernorm, layer.nar_mlp))
    groups = YuE2TokenLayers(torch.nn.ModuleList(ar)), YuE2AcousticLayers(torch.nn.ModuleList(acoustic))
    owned = [{id(tensor) for tensor in (*group.parameters(), *group.buffers())} for group in groups]
    expected = {id(tensor) for tensor in (*model.parameters(), *model.buffers())}
    if owned[0] & owned[1] or owned[0] | owned[1] != expected:
        raise ValueError("YuE2 offload groups must own every parameter and buffer exactly once")
    return groups


class ComfyResidency:
    def __init__(self, device, *, use_comfy_attention=False):
        self.device = torch.device(device)
        self.use_comfy_attention = use_comfy_attention
        self.offload_device = torch.device("cpu")
        self._patchers = {}
        self._synthesis_patchers = {}

    def move(self, model, device):
        device = torch.device(device)
        if device not in {self.device, self.offload_device}:
            raise ValueError("YuE2 residency only supports its selected device and CPU offload")
        patcher = self._patchers.get(model)
        if device == self.offload_device:
            if patcher is not None:
                model_management.unload_model_and_clones(patcher, all_devices=True)
            return model
        if patcher is None:
            patcher = ModelPatcher(_ModelContainer(model), self.device, self.offload_device)
            if self.use_comfy_attention:
                from .attention import patch_attention

                patch_attention(patcher, model)
            self._patchers[model] = patcher
        # Upstream modules have no Comfy cast hooks, so partial loading is unsupported.
        model_management.load_models_gpu([patcher], force_full_load=True)
        return model

    def move_synthesis(self, model, device):
        device = torch.device(device)
        if device not in {self.device, self.offload_device}:
            raise ValueError("YuE2 residency only supports its selected device and CPU offload")
        if self.use_comfy_attention:
            raise ValueError("Synthesis offload uses upstream attention; combined attention experiments are unsupported")
        patchers = self._synthesis_patchers.get(model)
        if device == self.offload_device:
            for patcher in patchers or ():
                model_management.unload_model_and_clones(patcher, all_devices=True)
            return model
        if patchers is None:
            patchers = [ModelPatcher(group, self.device, self.offload_device) for group in synthesis_groups(model)]
            self._synthesis_patchers[model] = patchers
        model_management.load_models_gpu(patchers, force_full_load=True)
        return model

    @contextmanager
    def offload_ar(self, model):
        patchers = self._synthesis_patchers[model]
        logging.info("[YuE2] Offloading token-generation layers for synthesis.")
        model_management.unload_model_and_clones(patchers[0], all_devices=True)
        yield
        # Keep acoustic layers resident while restoring AR for the next chunk.
        # On failure/cancellation the runtime unloads both groups instead.
        logging.info("[YuE2] Restoring token-generation layers.")
        model_management.load_models_gpu(patchers, force_full_load=True)

    def close(self):
        patchers, self._patchers = self._patchers, {}
        synthesis, self._synthesis_patchers = self._synthesis_patchers, {}
        try:
            with ExitStack() as cleanup:
                for patcher in [*patchers.values(), *(p for group in synthesis.values() for p in group)]:
                    cleanup.callback(model_management.unload_model_and_clones, patcher, all_devices=True)
        finally:
            patchers.clear()
            synthesis.clear()
