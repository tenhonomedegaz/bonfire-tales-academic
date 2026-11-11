import { container } from 'tsyringe';
import { GuildMemberRoleManager } from 'discord.js';
import ptBR, { format } from 'date-fns';

import { IDiscordAutocomplete } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { ShowUserQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowUserQuestsUseCase';
import { ShowOthersUsersQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowOthersUsersQuestsUseCase';
import deleteQuest from '@/modules/discord/commands/bonfire/rpg/quests/deleteQuest';

export const ownQuestsAutocomplete: IDiscordAutocomplete = {
  commandsToRespond: [deleteQuest.commandData.name],
  async execute(bot, interaction) {
    try {
      const { user, member } = interaction;
      const searchTerm = String(interaction.options.getFocused()).toLowerCase();

      if (!member) {
        await interaction.respond([]);
        return;
      }

      const showUserQuestsUseCase = container.resolve(ShowUserQuestsUseCase);

      // check admin role
      const requiredRoles = [bonfireRoles.adminRoleName];
      const userRoles = member.roles as GuildMemberRoleManager;
      const hasRole = userRoles.cache.some((role) => requiredRoles.includes(role.name));

      const quests = await showUserQuestsUseCase.execute({
        userId: user.id,
        searchTerm,
        limit: 25,
      });

      // append others quests response for admin be able to delete
      if (hasRole) {
        const showOthersUsersQuestsUseCase = container.resolve(ShowOthersUsersQuestsUseCase);

        const otherQuests = await showOthersUsersQuestsUseCase.execute({
          userIdToExclude: user.id,
          searchTerm,
          limit: 25,
        });

        quests.push(...otherQuests);
      }

      if (quests.length === 0) {
        await interaction.respond([]);
        return;
      }

      const result = quests.slice(0, 24).map((quest) => {
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
