import math

def estimate_download_size(da):
    """
    Estimate the download size of a DataArray subset when downloaded from Earth Data Hub. 
    Only works when the subset is continuous.

    Parameters:
    ----------
    da : xarray.DataArray
        The subset of the original DataArray being downloaded, before applying reductions.
    """
    
    # 1. Extract the base chunk shape from the selection's encoding
    encoding = da.encoding
    
    if 'preferred_chunks' in encoding:
        chunk_shape = encoding['preferred_chunks']
    elif 'chunks' in encoding:
        # Zarr chunks are usually stored as a tuple; zip them with dimension names
        chunk_shape = dict(zip(da.dims, encoding['chunks']))
    else:
        raise ValueError(
            "Original chunk shape is missing from the selection's encoding. "
            "Please ensure `.encoding` is preserved."
        )
    #print('chunk shape: ',chunk_shape)

    # 2. Count the number of chunks needed for each dimension
    needed_chunks = {key: len(value) for key, value in da.chunksizes.items()}
    # Calculate total number of chunks (including the dropped dimensions which require 1 chunk)
    total_chunks = math.prod(needed_chunks.get(dim, 1) for dim in chunk_shape)
    print(f'Needed chunks: {needed_chunks}. Total: {total_chunks}')
    
    # 3. Calculate the download shape. Use .get() to default any dropped dimension to 1 chunk.
    download_shape = {
        dim: chunk_shape[dim] * needed_chunks.get(dim, 1) 
        for dim in chunk_shape
    }
    #print('download shape:', download_shape)
    
    # 4. Calculate the total number of pixels in the download
    download_pixels = math.prod(download_shape.values())
    #print(f'download pixels: {download_pixels} pixels')


    # 5. Calculate estimated uncompressed and compressed sizes

    # Use .itemsize to safely get bytes per element (e.g., float32 = 4 bytes)
    uncompressed_download_size = da.dtype.itemsize * download_pixels
    #print(f'uncompressed download size: {round(uncompressed_download_size / (1024**2), 3):,} MiB')
    
    # Apply a 5% compression factor (EDH data compression estimate)
    compression_ratio = 5
    compressed_download_size = uncompressed_download_size/compression_ratio
    
    # Convert to GiB and MiB
    gib = compressed_download_size / (1024**3)
    mib = compressed_download_size / (1024**2)
    
    print(f'Estimated download size: {round(gib, 3):,} GiB ({round(mib, 0):,} MiB)')
