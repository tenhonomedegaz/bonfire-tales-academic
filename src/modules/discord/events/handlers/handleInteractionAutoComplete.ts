import { AutocompleteInteraction } from 'discord.js';

import { IBotEnhanced } from '@/modules/discord/types';
import { autocompleteHandlers } from '@/modules/discord/commands/autocomplete';

export async function handleInteractionAutoComplete(
  bot: IBotEnhanced,
  interaction: AutocompleteInteraction,
): Promise<void> {
  console.log("📌 Autocomplete incoming:", interaction.commandName);
  const { commandName } = interaction;

  const autocomplete = autocompleteHandlers.find((item) =>
    item.commandsToRespond.includes(commandName),
  );

  if (!autocomplete) {
    await interaction.respond([]);
    return;
  }

  try {
    await autocomplete.execute(bot, interaction);
  } catch (error) {
    bot.logger.log('error', `Erro ao tentar executar o autocomplete ${commandName}`, error);
  }
}