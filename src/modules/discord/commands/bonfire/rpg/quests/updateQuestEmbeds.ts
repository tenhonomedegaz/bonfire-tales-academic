import { container } from 'tsyringe';
import { Guild, TextChannel, EmbedBuilder } from 'discord.js';

import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { questInfoEmbedMessage } from './questEmbeds';

export async function updateQuestEmbeds(
  bot: any,
  guild: Guild | null,
  questId: string
): Promise<EmbedBuilder | null> {
  try {
    if (!guild) return null;

    const showQuestById = container.resolve(ShowQuestByIdUseCase);
    const quest = await showQuestById.execute(questId);

    if (!quest) return null;

    const newEmbed = await questInfoEmbedMessage({ quest, showQueueList: false });

    if (quest.isPublished && quest.channelId) {
      const channel = guild.channels.cache.get(quest.channelId) as TextChannel;

      if (channel && channel.isTextBased()) {
        try {
          bot.logger.log('info', 'updateQuestEmbeds: Updating quest ' + questId);
		  bot.logger.log('info', 'Channel ID: ' + quest.channelId);
		  bot.logger.log('info', 'Is Published: ' + quest.isPublished);
		  bot.logger.log('info', 'Players: ' + quest.questPlayers.map(p => p.userId + ':' + p.type).join(', '));
		  const msgs = await channel.messages.fetch({ limit: 50 });
		  bot.logger.log('info', 'Fetched messages: ' + msgs.size);
		  for (const m of msgs.values()) {
			bot.logger.log('info', 'Message embed footer: ' + (m.embeds?.[0]?.footer?.text || 'NONE'));
		  }
          const questMsg = msgs.find(
            (m) => m.embeds?.[0]?.footer?.text === String(quest.id)
          );

          if (questMsg) {
            await questMsg.edit({ embeds: [newEmbed] }).catch(() => {});
          }
        } catch (err) {
          bot.logger.log('warn', 'updateQuestEmbeds: failed to update mission channel message', err);
        }
      }
    }

    return newEmbed;
  } catch (err) {
    bot?.logger?.log('error', 'updateQuestEmbeds error', err);
    return null;
  }
}