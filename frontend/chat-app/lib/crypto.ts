import { openDB, DBSchema } from 'idb';

const DB_NAME = 'chat-e2ee-db';
const STORE_NAME = 'keys';
const KEY_PAIR_ID = 'master-key-pair';

interface ChatDB extends DBSchema {
  keys: {
    key: string;
    value: CryptoKeyPair;
  };
}

// --- IndexedDB Storage ---

export async function storeKeyPair(keyPair: CryptoKeyPair): Promise<void> {
  const db = await openDB<ChatDB>(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE_NAME);
    },
  });
  await db.put(STORE_NAME, keyPair, KEY_PAIR_ID);
}

export async function getKeyPair(): Promise<CryptoKeyPair | undefined> {
  const db = await openDB<ChatDB>(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE_NAME);
    },
  });
  return db.get(STORE_NAME, KEY_PAIR_ID);
}

// --- RSA Key Generation & Management ---

export async function generateKeyPair(): Promise<CryptoKeyPair> {
  return window.crypto.subtle.generateKey(
    {
      name: 'RSA-OAEP',
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256',
    },
    true, // extractable
    ['encrypt', 'decrypt']
  );
}

export async function exportPublicKey(key: CryptoKey): Promise<string> {
  const exported = await window.crypto.subtle.exportKey('spki', key);
  const exportedAsString = String.fromCharCode(...new Uint8Array(exported));
  const exportedAsBase64 = window.btoa(exportedAsString);
  return `-----BEGIN PUBLIC KEY-----\n${exportedAsBase64}\n-----END PUBLIC KEY-----`;
}

// --- AES Encryption/Decryption ---

export async function encryptMessage(
  text: string,
  recipientPublicKeys: { [userId: string]: string } // userId -> PEM string
): Promise<{
  ciphertext: string;
  iv: string;
  encrypted_keys: { [userId: string]: string };
}> {
  // 1. Generate random AES key
  const aesKey = await window.crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt']
  );

  // 2. Encrypt message with AES
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const encoder = new TextEncoder();
  const encodedText = encoder.encode(text);

  const encryptedContent = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    aesKey,
    encodedText
  );

  // 3. Encrypt AES key for each recipient
  const exportedAesKey = await window.crypto.subtle.exportKey('raw', aesKey);
  const encryptedKeys: { [userId: string]: string } = {};

  for (const [userId, pubKeyPem] of Object.entries(recipientPublicKeys)) {
    try {
      const publicKey = await importPublicKey(pubKeyPem);
      const encryptedAesKey = await window.crypto.subtle.encrypt(
        { name: 'RSA-OAEP' },
        publicKey,
        exportedAesKey
      );
      encryptedKeys[userId] = arrayBufferToBase64(encryptedAesKey);
    } catch (e) {
      console.error(`Failed to encrypt key for user ${userId}`, e);
    }
  }

  return {
    ciphertext: arrayBufferToBase64(encryptedContent),
    iv: arrayBufferToBase64(iv),
    encrypted_keys: encryptedKeys,
  };
}

export async function decryptMessage(
  ciphertextB64: string,
  ivB64: string,
  encryptedKeyB64: string,
  privateKey: CryptoKey
): Promise<string> {
  try {
    // 1. Decrypt AES key
    const encryptedKey = base64ToArrayBuffer(encryptedKeyB64);
    const aesKeyRaw = await window.crypto.subtle.decrypt(
      { name: 'RSA-OAEP' },
      privateKey,
      encryptedKey
    );

    const aesKey = await window.crypto.subtle.importKey(
      'raw',
      aesKeyRaw,
      { name: 'AES-GCM' },
      false,
      ['decrypt']
    );

    // 2. Decrypt Content
    const ciphertext = base64ToArrayBuffer(ciphertextB64);
    const iv = base64ToArrayBuffer(ivB64);

    const decryptedContent = await window.crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      aesKey,
      ciphertext
    );

    const decoder = new TextDecoder();
    return decoder.decode(decryptedContent);
  } catch (e) {
    console.error('Decryption failed:', e);
    return '[Decryption Error]';
  }
}

// --- Helpers ---

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary_string = window.atob(base64);
  const len = binary_string.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary_string.charCodeAt(i);
  }
  return bytes.buffer;
}

async function importPublicKey(pem: string): Promise<CryptoKey> {
  // fetch the part of the PEM string between header and footer
  const pemHeader = '-----BEGIN PUBLIC KEY-----';
  const pemFooter = '-----END PUBLIC KEY-----';
  const pemContents = pem.substring(
    pem.indexOf(pemHeader) + pemHeader.length,
    pem.indexOf(pemFooter)
  );
  // base64 decode the string to get the binary data
  const binaryDerString = window.atob(pemContents.replace(/\s/g, ''));
  // convert from a binary string to an ArrayBuffer
  const binaryDer = new Uint8Array(binaryDerString.length);
  for (let i = 0; i < binaryDerString.length; i++) {
    binaryDer[i] = binaryDerString.charCodeAt(i);
  }

  return window.crypto.subtle.importKey(
    'spki',
    binaryDer.buffer,
    {
      name: 'RSA-OAEP',
      hash: 'SHA-256',
    },
    true,
    ['encrypt']
  );
}
