# Future Diffusion Training

**Not in v1.** No model is trained here. The learning corpus produces a
dataset. It does not produce a model.

Out of scope today:

- embeddings
- tokenizer
- graph neural network
- diffusion model
- training loop
- GPU
- Modal

`cloudforge learn export-training` writes a versioned JSON/JSONL bundle plus a
coverage manifest. Not a checkpoint, not weights.

A future generator that consumed this corpus would still have to pass the
local [validation pipeline](Validation-Pipeline.md).
