import express from 'express';
import { chunkText } from '../utils/chunker.js';
import { getEmbedding } from '../utils/embedder.js';
import { uploadJSONToStoracha } from '../services/storacha.js';
import { addChunkToIndex, querySimilarChunks } from '../services/vectorstore.js';
import axios from 'axios';
import dotenv from 'dotenv';
import multer from 'multer';
import pdfParse from 'pdf-parse';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const cheerio = require('cheerio');import fs from 'fs';

dotenv.config();

const router = express.Router();

// Mistral API config
const MISTRAL_API_KEY = process.env.MISTRAL_API_KEY;
const MISTRAL_API_URL = 'https://api.mistral.ai/v1/chat/completions';

// Set up multer for file uploads
const upload = multer({ dest: 'uploads/' });

// ✅ Upload and index text, PDF, or URL
router.post('/upload', upload.single('file'), async (req, res) => {
  const { type } = req.body;
  let text;

  // Handle different input types
  if (type === 'text') {
    if (!req.body.content) {
      return res.status(400).json({ error: 'Content is required for type "text"' });
    }
    text = req.body.content;
  } else if (type === 'pdf') {
    if (!req.file) {
      return res.status(400).json({ error: 'File is required for type "pdf"' });
    }
    try {
      const dataBuffer = fs.readFileSync(req.file.path);
      const pdfData = await pdfParse(dataBuffer);
      text = pdfData.text;
      // Clean up temporary file
      fs.unlinkSync(req.file.path);
    } catch (err) {
      console.error('Error processing PDF:', err);
      return res.status(500).json({ error: 'Failed to process PDF' });
    }
  } 
  else if (type === 'url') {
    if (!req.body.url) {
      return res.status(400).json({ error: 'URL is required for type "url"' });
    }
    const url = req.body.url;
    try {
      const response = await axios.get(url, { timeout: 10000 }); // 10-second timeout
      const html = response.data;
      const $ = cheerio.load(html);
      text = $('body').text().replace(/\s+/g, ' ').trim();
    } catch (err) {
      console.error('Error fetching URL:', err);
      return res.status(500).json({ error: 'Failed to fetch content from URL' });
    }
  } 
  else {
    return res.status(400).json({ error: 'Invalid type. Must be "text", "pdf", or "url"' });
  }

  // Process the text: chunk, embed, upload, and index
  const chunks = chunkText(text, 3000);
  const results = [];

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];
    const embedding = await getEmbedding(chunk);
    const filename = `chunk-${i}.json`;
    const jsonObj = { id: `chunk-${i}`, content: chunk };
    const cid = await uploadJSONToStoracha(jsonObj, filename);
    await addChunkToIndex(cid, embedding, { index: i, filename });

    results.push({ cid, filename, preview: chunk.slice(0, 120) });
  }

  res.json({ uploaded: results });
});

// 🔍 Query and get answer from Mistral
// 🔍 Query and get answer from Mistral
router.post('/query', async (req, res) => {
  const { question } = req.body;

  const queryEmbedding = await getEmbedding(question);
  const results = await querySimilarChunks(queryEmbedding, 1);

  const topCIDs = results.ids[0];
  const topMetas = results.metadatas[0];

  const docs = await Promise.all(
    topCIDs.map(async (cid, index) => {
      const meta = topMetas[index];
      const filename = meta?.filename;

      if (!filename) return null;

      const gateways = [
        `https://${cid}.ipfs.w3s.link/${filename}`,
        `https://ipfs.io/ipfs/${cid}/${filename}`
      ];

      for (const url of gateways) {
        try {
          const file = await axios.get(url, { timeout: 7000 });
          return file.data;
        } catch (err) {
          console.warn(`❌ Failed to fetch from: ${url}`);
        }
      }

      return null;
    })
  );

  const validDocs = docs.filter(Boolean);
  const bestMatch = validDocs.map(d => d.content).join('\n\n');

  // ✨ If no relevant context is found, let Mistral answer normally
  const prompt = validDocs.length > 0
    ? `Use the following knowledge to answer the question:\n\nKnowledge: ${bestMatch}\n\nQuestion: ${question}\n\nAnswer:`
    : `Question: ${question}\n\nAnswer:`;

  try {
    const headers = { Authorization: `Bearer ${MISTRAL_API_KEY}` };
    const data = {
      model: 'open-mistral-nemo',
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 200
    };

    const response = await axios.post(MISTRAL_API_URL, data, { headers });

    if (response.status === 200) {
      const answer = response.data.choices[0].message.content;
      return res.json({
        answer,
        context: validDocs.length > 0 ? validDocs : []
      });
    } else {
      return res.status(500).json({ error: 'Mistral API failed' });
    }
  } catch (err) {
    console.error('🔻 Mistral error:', err.message);
    return res.status(500).json({ error: 'Failed to generate response from Mistral' });
  }
});


export default router;
