import { readFile } from 'node:fs/promises';

import type { WASocket } from 'baileys';

import type { OutboundAction } from '../../core/runtime.js';

export async function handleOutboundActions(
  sock: WASocket,
  chatId: string,
  actions: OutboundAction[]
): Promise<void> {
  for (const action of actions) {
    await handleOutboundAction(sock, chatId, action);
  }
}

export async function handleOutboundAction(
  sock: WASocket,
  chatId: string,
  action: OutboundAction
): Promise<void> {
  switch (action.type) {
    case 'send_text': {
      await sock.sendMessage(
        chatId,
        { text: action.text },
        action.replyToMessageId
          ? {
              quoted: {
                key: {
                  remoteJid: chatId,
                  id: action.replyToMessageId,
                  fromMe: false,
                },
              },
            }
          : undefined
      );
      return;
    }

    case 'send_image': {
      const buffer = await readFile(action.storagePath);
      await sock.sendMessage(chatId, {
        image: buffer,
        caption: action.caption,
        mimetype: action.mimeType,
      });
      return;
    }

    case 'send_audio': {
      const buffer = await readFile(action.storagePath);
      await sock.sendMessage(chatId, {
        audio: buffer,
        mimetype: action.mimeType,
        ptt: action.ptt ?? false,
      });
      return;
    }

    case 'send_video': {
      const buffer = await readFile(action.storagePath);
      await sock.sendMessage(chatId, {
        video: buffer,
        caption: action.caption,
        mimetype: action.mimeType,
      });
      return;
    }

    case 'send_document': {
      const buffer = await readFile(action.storagePath);
      await sock.sendMessage(chatId, {
        document: buffer,
        fileName: action.fileName,
        caption: action.caption,
        mimetype: action.mimeType,
      });
      return;
    }

    case 'ignore': {
      return;
    }

    default: {
      const exhaustiveCheck: never = action;
      throw new Error(
        `Unsupported outbound action: ${JSON.stringify(exhaustiveCheck)}`
      );
    }
  }
}
