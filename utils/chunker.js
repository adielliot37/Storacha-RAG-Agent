import fs from 'fs';

export function chunkText(filePath, chunkSize = 500) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const sentences = raw.match(/[^\.!\?]+[\.!\?]+/g) || [raw];
  const chunks = [];

  let current = '';
  for (const sentence of sentences) {
    if ((current + sentence).length > chunkSize) {
      chunks.push(current.trim());
      current = sentence;
    } else {
      current += sentence;
    }
  }
  if (current) chunks.push(current.trim());
  return chunks;
}
