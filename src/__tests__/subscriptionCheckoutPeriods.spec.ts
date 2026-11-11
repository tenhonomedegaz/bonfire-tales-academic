import { createSubscriptionInfoEmbedMessages } from '@/modules/discord/commands/bonfire/subscription/subscriptionEmbeds';
import { bonfireSubscriptionOffers } from '@/config/bonfire';

jest.mock('@/shared/env', () => ({ env: {
  BONFIRE_SITE_URL: 'https://example.test',
  BONFIRE_CHECKOUT_SIGNING_SECRET: 'isolated-test-signing-key',
} }));

describe('Colab checkout periods', () => {
  it('signs the selected period and keeps long plans non-recurring', () => {
    const embeds = createSubscriptionInfoEmbedMessages({ discordUserId: '123456789012345678' });
    const text = embeds.map(embed => embed.toJSON().description || '').join('\n');
    const links = [...text.matchAll(/https:\/\/example\.test\/colaborador\/discord\/\?token=([^\s)]+)/g)];
    const payloads = links.map(link => JSON.parse(Buffer.from(link[1].split('.')[0], 'base64url').toString()));
    for (const offer of bonfireSubscriptionOffers) {
      expect(payloads).toEqual(expect.arrayContaining([expect.objectContaining({ product: offer.id, mode: 'single' })]));
      if (offer.months > 1) expect(payloads.some(p => p.product === offer.id && p.mode === 'recurring')).toBe(false);
    }
    for (const tier of ['conde', 'marques', 'duque']) {
      expect(payloads).toEqual(expect.arrayContaining([expect.objectContaining({ product: `colaborador-${tier}-1m`, mode: 'recurring' })]));
    }
  });

  it('matches monthly totals, discounts and product duration', () => {
    for (const offer of bonfireSubscriptionOffers) {
      const monthly = bonfireSubscriptionOffers.find(p => p.tier === offer.tier && p.months === 1)!;
      const discount = ({ 1: 0, 3: 0.1, 6: 0.15, 12: 0.25 } as Record<number, number>)[offer.months];
      expect(offer.price).toBeCloseTo(monthly.price * offer.months * (1 - discount), 2);
      expect(offer.id).toMatch(new RegExp(`-${offer.months}m$`));
      expect(offer.bonusDays).toBe(0);
    }
  });
});
