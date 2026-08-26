# ============================================================
# S2 PATCH INSTRUCTIONS FOR app/context/representation.py
# ============================================================
#
# DO NOT overwrite the existing file. Instead, make these
# minimal additions to the existing representation.py:
#
# 1. Add import at the top:
#
#    from app.context.compressor import build_compressed_context
#
# 2. Add a new representer function:
#
#    def represent_compressed_v1(chunks: list, **kwargs) -> str:
#        """S2: Compressed context representation."""
#        max_chars = kwargs.get("max_chunk_chars", 400)
#        dedup = kwargs.get("dedup_threshold", 0.90)
#        return build_compressed_context(
#            chunks,
#            max_chunk_chars=max_chars,
#            dedup_threshold=dedup,
#        )
#
# 3. Register it in the REPRESENTERS dict (or equivalent dispatch):
#
#    REPRESENTERS["compressed_v1"] = represent_compressed_v1
#
# That's it. The existing "flat" representer must remain untouched.
# ============================================================
