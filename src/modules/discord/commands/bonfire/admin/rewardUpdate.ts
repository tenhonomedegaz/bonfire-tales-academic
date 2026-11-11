import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';
import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { questRewardEmbedMessage } from '@/modules/discord/commands/bonfire/rpg/quests/questEmbeds';
import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { recordParticipantRewards } from '@/modules/rpg/quests/services/questReward';

async function resolveQuestFromInput(input: string): Promise<Quest | null> {
  const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
  const questById = await showQuestByIdUseCase.execute(input).catch(() => null);
  if (questById) {
    return questById;
  }

  const showPublishedQuestsUseCase = container.resolve(ShowPublishedQuestsUseCase);
  const quests = await showPublishedQuestsUseCase.execute({
    searchTerm: input,
    limit: 25,
    questStatus: ['finished'],
  });

  const normalizedInput = input.trim().toLowerCase();

  return (
    quests.find((quest) => quest.name.toLowerCase() === normalizedInput) ||
    quests.find((quest) => quest.name.toLowerCase().includes(normalizedInput)) ||
    null
  );
}

const commandData = new SlashCommandBuilder()
  .setName('reward-update')
  .setDescription('🔧 Altera a quantidade de aventuras de recompensa de uma missão')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missão').setAutocomplete(true).setRequired(true),
  )
  .addIntegerOption((option) =>
    option.setName('aventuras').setDescription('Nova quantidade de aventuras (recompensa)').setMinValue(0).setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [
    bonfireRoles.adminRoleName,
  ],
  rootAdminOnly: true,
  cooldown: 5000,
  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: false });

      const { user, guild } = interaction;
      if (!guild) {
        await interaction.followUp({ content: 'Servidor não encontrado.' });
        return;
      }

      const questInput = interaction.options.getString('missao', true);
      const aventuras = interaction.options.getInteger('aventuras', true);
      const quest = await resolveQuestFromInput(questInput);

      if (!quest) {
        await interaction.followUp({ content: 'Missão não encontrada.' });
        return;
      }

      if (quest.status !== 'finished') {
        await interaction.followUp({ content: 'Só é possível atualizar recompensa de missões já finalizadas.' });
        return;
      }

      quest.rewardAventurasOverride = aventuras;
      recordParticipantRewards(quest, aventuras, 'staff_override', new Date().toISOString());

      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
      const updatedQuest = await updateQuestUseCase.execute(quest);

      const rewardEmbed = await questRewardEmbedMessage({ quest: updatedQuest, guild });

      await interaction.followUp({
        content: `🔧 **Recompensa Atualizada**\nO administrador <@${user.id}> atualizou a recompensa da missão **${quest.name}** para **${aventuras} aventura(s)**.`,
        embeds: [rewardEmbed],
      });

    } catch (error) {
      bot.logger.log('error', 'Erro ao rodar /reward-update', error);
      await interaction.followUp({ content: 'Falha ao atualizar as recompensas da missão.' });
    }
  },
};

export default command;
