import { createHmac } from 'node:crypto';

import { EmbedBuilder } from 'discord.js';

import { Colors } from '@/config/discord';
import { thumbnails } from '@/config/bonfire';
import { env } from '@/shared/env';

type CheckoutIdentity = {
  discordUserId: string;
  discordUsername?: string;
};

function checkoutUrl(
  identity: CheckoutIdentity | undefined,
  product: string,
  mode: 'single' | 'recurring',
  fallbackUrl: string,
): string {
  if (!identity?.discordUserId || !env.BONFIRE_CHECKOUT_SIGNING_SECRET) return fallbackUrl;

  const payload = Buffer.from(JSON.stringify({
    discord_id: identity.discordUserId,
    discord_name: identity.discordUsername || '',
    product,
    mode,
    exp: Math.floor(Date.now() / 1000) + 30 * 60,
  })).toString('base64url');
  const signature = createHmac('sha256', env.BONFIRE_CHECKOUT_SIGNING_SECRET)
    .update(payload)
    .digest('base64url');
  return `${env.BONFIRE_SITE_URL.replace(/\/$/, '')}/colaborador/discord/?token=${payload}.${signature}`;
}

export function createSubscriptionInfoEmbedMessages(identity?: CheckoutIdentity): EmbedBuilder[] {
  const embedMessageData10 = [
    `**Assinatura**`,
    `[CARTÃO](${checkoutUrl(identity, 'colaborador-conde-1m', 'recurring', 'https://www.asaas.com/c/8875kbi9lmlnbpbs')})`,
    `**Pagamento único**`,
    `[PIX / BOLETO / CARTÃO](${checkoutUrl(identity, 'colaborador-conde-1m', 'single', 'https://www.asaas.com/c/0d19cyn73or5ee4m')})`,
    ``,
	
	`💸 **Planos Trimestral, Semestral e Anual**`,
	`[**Trimestral** (10% OFF)](${checkoutUrl(identity, 'colaborador-conde-3m', 'single', 'https://www.asaas.com/c/gggvz2l87g6ah4rs')})`,
	`[**Semestral** (15% OFF)](${checkoutUrl(identity, 'colaborador-conde-6m', 'single', 'https://www.asaas.com/c/74zeloshnmy8qf6d')})`,
	`[**Anual** (25% OFF)](${checkoutUrl(identity, 'colaborador-conde-12m', 'single', 'https://www.asaas.com/c/8kbe3dbsjx5tl9c5')})`,
	``,
	
    `**📌 Preferencia em Filas de missões**`,
    `(A partir do rank Ametista)`,
  ];

  const embedMessage10 = new EmbedBuilder()
    .setThumbnail(thumbnails.crown1)
    .setColor(Colors.green500)
    .setTitle(`👑 **Conde / Condessa:  (R$ 19,90)**`)
    .setDescription(embedMessageData10.join('\n'));

  // const buttonRow10 = new ActionRowBuilder().addComponents(
  //   new ButtonBuilder()
  //     .setURL('PREENCHER')
  //     .setLabel('CARTÃO (Assinatura) R$ 19,90')
  //     .setStyle(ButtonStyle.Link),
  //   new ButtonBuilder()
  //     .setURL('PREENCHER')
  //     .setLabel('PIX / BOLETO R$ 19,90')
  //     .setStyle(ButtonStyle.Link),
  // );

  const embedMessageData15 = [
    `**Assinatura**`,
    `[CARTÃO](${checkoutUrl(identity, 'colaborador-marques-1m', 'recurring', 'https://www.asaas.com/c/2icusjwxwyth44dl')})`,
    `**Pagamento único**`,
    `[PIX / BOLETO / CARTÃO](${checkoutUrl(identity, 'colaborador-marques-1m', 'single', 'https://www.asaas.com/c/vdc8h0lg9c6ni55z')})`,
    ``,
	
	`💸 **Planos Trimestral, Semestral e Anual**`,
	`[**Trimestral** (10% OFF)](${checkoutUrl(identity, 'colaborador-marques-3m', 'single', 'https://www.asaas.com/c/ckm5u78s3yhkztf4')})`,
	`[**Semestral** (15% OFF)](${checkoutUrl(identity, 'colaborador-marques-6m', 'single', 'https://www.asaas.com/c/js1wn7vwapvcis2k')})`,
	`[**Anual** (25% OFF)](${checkoutUrl(identity, 'colaborador-marques-12m', 'single', 'https://www.asaas.com/c/mo3xjc7myj5q67g7')})`,
	``,
	
    `**+1 👥 Slot de personagem durante o mês**`,
    `(Limite de +1, fora os que você pode ganhar em níveis específicos)`,
    `**📌 Preferencia em Filas de missões**`,
    `(A partir do rank Ametista)`,
    `**+1 ⚔️ Missão Especial (Mensal)**`,
  ];

  const embedMessage15 = new EmbedBuilder()
    .setThumbnail(thumbnails.crown2)
    .setColor(Colors.green500)
    .setTitle(`👑 **Marquês / Marquesa: (R$ 29,90)**`)
    .setDescription(embedMessageData15.join('\n'));

  // const buttonRow15 = new ActionRowBuilder().addComponents(
  //   new ButtonBuilder()
  //     .setURL('PREENCHER')
  //     .setLabel('CARTÃO (Assinatura) R$ 29,90')
  //     .setStyle(ButtonStyle.Link),
  //   new ButtonBuilder()
  //     .setURL('PREENCHER')
  //     .setLabel('PIX / BOLETO R$ 29,90')
  //     .setStyle(ButtonStyle.Link),
  // );

  const embedMessageData20 = [
    `**Assinatura**`,
    `[CARTÃO](${checkoutUrl(identity, 'colaborador-duque-1m', 'recurring', 'https://www.asaas.com/c/p7ne3agr03yphhqx')})`,
    `**Pagamento único**`,
    `[PIX / BOLETO / CARTÃO](${checkoutUrl(identity, 'colaborador-duque-1m', 'single', 'https://www.asaas.com/c/ir2nwmgt3s950e02')})`,
    ``,
	
	`💸 **Planos Trimestral, Semestral e Anual**`,
	`[**Trimestral** (10% OFF)](${checkoutUrl(identity, 'colaborador-duque-3m', 'single', 'https://www.asaas.com/c/m7uakneidrvso7a9')})`,
	`[**Semestral** (15% OFF)](${checkoutUrl(identity, 'colaborador-duque-6m', 'single', 'https://www.asaas.com/c/en2ibwj3r29s77ig')})`,
	`[**Anual** (25% OFF)](${checkoutUrl(identity, 'colaborador-duque-12m', 'single', 'https://www.asaas.com/c/hojk0lk7zssxsa8w')})`,
	``,
	
    `**+1 👥 Slot de personagem durante o período**`,
    `(Limite de +1, fora os que você pode ganhar em níveis específicos)`,
    `**📌 Preferencia em Filas de missões**`,
    `(A partir do rank Ametista)`,
    `**+1 ⚔️ Missão Especial (Mensal)**`,
    `**+1 💥 Boost para uma missão (Mensal)**`,
    `🔒 Possibilidade de colocar 1 personagem no cofre durante o mês`,
  ];

  const embedMessage20 = new EmbedBuilder()
    .setThumbnail(thumbnails.crown3)
    .setColor(Colors.green500)
    .setTitle(`👑 **Duque / Duquesa: (R$ 39,90)**`)
    .setDescription(embedMessageData20.join('\n'));

  // const buttonRow20 = new ActionRowBuilder().addComponents(
  //   new ButtonBuilder()
  //     .setURL('PREENCHER')
  //     .setLabel('CARTÃO (Assinatura) R$ 39,90')
  //     .setStyle(ButtonStyle.Link),
  //   new ButtonBuilder()
  //     .setURL('PREENCHER')
  //     .setLabel('PIX / BOLETO R$ 39,90')
  //     .setStyle(ButtonStyle.Link),
  // );

  const embedMessageDataPackages = [
    `Caso queira, temos também a possibilidade da compra dos tokens de Missão Especial, Boost e Superboost à parte dos pacotes de colaboração.`,
    ``,
    `[+1 ⚔️ Missão Especial (R$ 14,90)](${checkoutUrl(identity, 'token-missao', 'single', 'https://www.asaas.com/c/4i2hskg41p4mszkg')})`,
    `[+1 💥 Boost para uma missão (R$ 19,90)](${checkoutUrl(identity, 'token-boost', 'single', 'https://www.asaas.com/c/seyli68v427zvbds')})`,
	`[+1 🚀 Superboost para uma missão (R$ 69,90)](${checkoutUrl(identity, 'token-superboost', 'single', 'https://www.asaas.com/c/69cthesmlfcu15th')})`,
  ];

  const embedMessagePackages = new EmbedBuilder()
    .setThumbnail(thumbnails.gems)
    .setColor(Colors.green500)
    .setTitle(`⭐ **Tokens**`)
    .setDescription(embedMessageDataPackages.join('\n'));

  const subscriptionEmbeds = [embedMessage10, embedMessage15, embedMessage20, embedMessagePackages];

  return subscriptionEmbeds;
}
