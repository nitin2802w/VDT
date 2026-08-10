def chunk_data(data: bytes, block_size: int = 400) -> tuple[list[bytes], int]:
    """
    Splits data into a list of fixed-size blocks, padding the last block with zeros if necessary.
    Returns the list of blocks and the original unpadded file size.
    """
    file_size = len(data)
    blocks = []
    
    if file_size == 0:
        return blocks, file_size
        
    for i in range(0, file_size, block_size):
        block = data[i:i + block_size]
        if len(block) < block_size:
            # Pad the final block with zeros
            block = block + b'\x00' * (block_size - len(block))
        blocks.append(block)
        
    return blocks, file_size

def reconstruct_data(blocks: list[bytes], file_size: int) -> bytes:
    """
    Concatenates a list of blocks and trims any padding to match the original file size.
    """
    if not blocks:
        return b""
        
    joined_data = b"".join(blocks)
    return joined_data[:file_size]

