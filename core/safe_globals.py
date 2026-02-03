"""Safe globals registration for torch serialization."""

import typing
import collections
import pathlib

_registered = False


def register_safe_globals():
    """
    Register safe globals for torch.load with weights_only=True.

    This function registers types that are commonly found in pyannote
    and whisperx model checkpoints, allowing safe deserialization.

    This function is idempotent - calling it multiple times has no effect
    after the first call.
    """
    global _registered
    if _registered:
        return

    import torch

    # Import omegaconf types
    from omegaconf import OmegaConf
    from omegaconf.listconfig import ListConfig
    from omegaconf.dictconfig import DictConfig
    from omegaconf.base import ContainerMetadata, Metadata
    from omegaconf.nodes import AnyNode

    # Import pyannote types
    from pyannote.audio.core.task import Specifications, Problem, Resolution
    from pyannote.audio.core.model import Introspection

    safe_globals = [
        # torch
        torch.torch_version.TorchVersion,

        # omegaconf (often inside pyannote checkpoints)
        OmegaConf,
        ListConfig,
        DictConfig,
        ContainerMetadata,
        Metadata,
        AnyNode,

        # pyannote task types
        Specifications,
        Problem,
        Resolution,
        Introspection,

        # typing / builtins
        typing.Any,
        list,
        dict,
        tuple,
        set,

        # common containers/types that may appear with weights_only
        pathlib.Path,
        collections.OrderedDict,
        collections.defaultdict,
        int,
        float,
        str,
        bool,
    ]

    torch.serialization.add_safe_globals(safe_globals)
    _registered = True
