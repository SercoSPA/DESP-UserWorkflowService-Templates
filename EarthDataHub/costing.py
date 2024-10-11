import math

def estimate_download_size(origin, selection):    
    base_chunk_shape = {key:value[0] for key,value in origin.chunksizes.items()}
    #print('base_chunk_shape: ',base_chunk_shape)
    
    needed_chunks_count_by_dim = {key:len(value) for key,value in selection.chunksizes.items()}
    for key in origin.chunksizes.keys():
        if key not in needed_chunks_count_by_dim.keys():
            needed_chunks_count_by_dim.update({key:1})
    #print('needed_chunks_count_by_dim: ',needed_chunks_count_by_dim)
    #print("total number of needed chunks: ", math.prod([val for val in needed_chunks_count_by_dim.values()]))
    
    estimated_download_shape = {key: base_chunk_shape[key]*needed_chunks_count_by_dim[key] for key in origin.chunksizes}
    #print('estimated_download_shape: ', estimated_download_shape) 
    
    estimated_download_fields = math.prod(estimated_download_shape[key] for key in estimated_download_shape)
    #print('estimated_download_fields : ', estimated_download_fields)

    estimated_dowload_size = int(str(selection.dtype)[-2:])//8*estimated_download_fields
    print(f'estimated_needed_chunks: {math.prod([val for val in needed_chunks_count_by_dim.values()])}')
    print(f'estimated_memory_size: {round(estimated_dowload_size/1000**3, 3):,} GB')
    print(f'estimated_download_size: {round(estimated_dowload_size/1000**3/10, 3):,} GB')