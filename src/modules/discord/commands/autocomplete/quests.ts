import { container } from 'tsyringe';
import ptBR, { format } from 'date-fns';

import { IDiscordAutocomplete } from '@/modules/discord/types';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';


export const questsAutocomplete: IDiscordAutocomplete = {
  commandsToRespond: [
    'reward-update',
    'missao-controles',
    'missao-fila',
    'missao-add-player',
    'missao-drop-player',
    'missao-excluir',
    'missao-pick',
    'missao-reagendar',
    'editar-missao',
    'missao-rank',
    'missao-tags',
  ],

  async execute(bot, interaction) {
    try {
      const searchTerm = String(interaction.options.getFocused()).toLowerCase();

      const showPublishedQuestsUseCase = container.resolve(ShowPublishedQuestsUseCase);

      const autocompleteFilters: Record<string, any> = {};

      if (interaction.commandName === 'reward-update') {
        autocompleteFilters.questStatus = ['finished'];
      } else if (['missao-add-player', 'missao-drop-player', 'missao-tags'].includes(interaction.commandName)) {
        autocompleteFilters.questStatus = ['idle', 'running', 'paused', 'frozen', 'finished'];
      } else if (interaction.commandName === 'missao-reagendar') {
        autocompleteFilters.questStatus = ['idle'];
      }

      const quests = await showPublishedQuestsUseCase.execute({
        searchTerm,
        limit: 25,
        ...autocompleteFilters,
      });

      if (quests.length === 0) {
        await interaction.respond([]);
        return;
      }

      const result = quests.map((quest) => {
        const formatedQuestDate = format(quest.questDate, 'dd/MM/yyyy HH:mm', {
          locale: ptBR,
        });

        return {
          name: `${formatedQuestDate} - ${quest.name}`,
          value: quest.id,
        };
      });

      await interaction.respond(result);
    } catch (error) {
      bot.logger.log('error', `Autocomplete (${interaction.commandName}) error`, error);
    }
  },
};
