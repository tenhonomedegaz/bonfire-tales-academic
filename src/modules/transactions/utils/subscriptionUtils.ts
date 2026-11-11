import { addMonths, addDays } from 'date-fns';
import { bonfireSubscriptionOffers } from '@/config/bonfire';
import { nowInBrazil } from '@/shared/util/dateTime';


/**
 * Returns the subscription offer object matching the internal ID.
 */
export function findSubscriptionOfferById(id: string) {
  return bonfireSubscriptionOffers.find((o) => o.id === id) ?? null;
}

/**
 * Computes the expiration date of a subscription based on:
 *   - offer.months
 *   - offer.bonusDays
 *
 * Falls back to +30 days if the plan ID is unknown.
 */
export function computeExpirationFromOfferId(offerId: string, now = nowInBrazil()): Date {
  const offer = findSubscriptionOfferById(offerId);

  if (!offer) {
    // Fallback logic (should never be used unless bad plan ID)
    const fallback = addDays(now, 30);
    fallback.setHours(0, 0, 0, 0);
    return fallback;
  }

  let expiration = addMonths(now, offer.months);
  expiration = addDays(expiration, offer.bonusDays);

  // Normalize for timezone consistency
  expiration.setHours(0, 0, 0, 0);

  return expiration;
}