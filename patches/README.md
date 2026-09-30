# L5 relation-extraction dependencies

`l5_relations.py` uses ReLiK and GLiREL from local clones under `other/`,
which git ignores. Install them into the service env without their pinned
dependencies, because those would replace the ROCm torch and transformers 5:

```bash
P=/mnt/data/miniconda3/envs/py310_amd/bin/python
git clone https://github.com/jackboyla/GLiREL.git other/GLiREL      # tested at 1f485a2
git clone https://github.com/SapienzaNLP/relik.git other/relik      # tested at 850da1c
git -C other/relik apply ../../patches/relik-transformers5.patch
$P -m pip install --no-deps -e ./other/GLiREL -e ./other/relik
$P -m pip install seqeval art pprintpp
$P -m pip install --no-deps https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

`relik-transformers5.patch` makes ReLiK run on transformers >= 5:
- adds its own copy of `PoolerEndLogits`, which transformers 5 removed
- builds the backbone with `from_config`
- calls `post_init()`
- adds `is_decoder` defaults
- sizes the word embeddings from the checkpoint

Without the last fix, the padded 128128-row checkpoint embeddings are
silently skipped as a size mismatch, and the reader then finds nothing.

For an already-installed systemd unit, also install `z3-backend-mcp-l5.conf`
as a drop-in (see the comments in that file).
