import { ChromaClient } from 'chromadb';

const client = new ChromaClient();
const collection = await client.getOrCreateCollection({ name: 'rag_chunks' });

export async function addChunkToIndex(cid, embedding, metadata) {
  await collection.add({
    ids: [cid],
    embeddings: [embedding],
    metadatas: [metadata],
  });
}

export async function querySimilarChunks(queryEmbedding, topK = 1) {
  
  return await collection.query({
    queryEmbeddings: [queryEmbedding],
    nResults: topK,
  });
}
