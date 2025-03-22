import * as Client from '@web3-storage/w3up-client';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';

dotenv.config();

const client = await Client.create();
await client.login(process.env.W3UP_EMAIL);
await client.setCurrentSpace(process.env.CURRENT_SPACE_DID);

export async function uploadJSONToStoracha(jsonObject, filename = 'chunk.json') {
  const tempPath = path.join('./', filename);
  fs.writeFileSync(tempPath, JSON.stringify(jsonObject));

  const { filesFromPaths } = await import('files-from-path');
  const files = await filesFromPaths([tempPath]);
  const cid = await client.uploadDirectory(files);

  fs.unlinkSync(tempPath); // Clean up
  return cid.toString();
}
