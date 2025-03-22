import express from 'express';
import dotenv from 'dotenv';
import ragRoutes from './routes/rag.js';

dotenv.config();

const app = express();
app.use(express.json());

app.use('/rag', ragRoutes);

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`🔮 RAG API running at http://localhost:${PORT}`);
});
