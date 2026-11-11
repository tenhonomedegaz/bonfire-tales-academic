import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags, TextChannel } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { bonfireRoles } from '@/config/bonfire';
import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { hasBotAdminPermission } from '@/modules/discord/util';

const objectIdRegex = /^(?:[a-f\d]{24}|c[a-z0-9]{24})$/i;

async function resolveQuestFromInput(input: string): Promise<Quest | null> {
  if (objectIdRegex.test(input)) {
    const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
    return showQuestByIdUseCase.execute(input);
  }

  const showPublishedQuestsUseCase = container.resolve(ShowPublishedQuestsUseCase);
  const quests = await showPublishedQuestsUseCase.execute({
    searchTerm: input,
    limit: 25,
  });

  const normalizedInput = input.trim().toLowerCase();

  return (
    quests.find((quest) => quest.name.toLowerCase() === normalizedInput) ||
    quests.find((quest) => quest.name.toLowerCase().includes(normalizedInput)) ||
    null
  );
}

const updateQuestRankCommandData = new SlashCommandBuilder()
  .setName('missao-rank')
  .setDescription('Atualiza os ranks permitidos em uma missão e notifica os novos cargos.')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Selecione a missão').setAutocomplete(true).setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('novos_ranks').setDescription('Mencione os novos ranks permitidos (ex: @Ametista @Topázio)').setRequired(true),
  );

const updateQuestRankCommand: IDiscordCommand = {
  commandData: updateQuestRankCommandData,
  allowedRoles: [
    bonfireRoles.masterRoleName,
    bonfireRoles.testMasterRoleName,
    bonfireRoles.adminRoleName,
    bonfireRoles.moderatorRoleName,
  ],
  cooldown: 5 * 1000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      const { user, guild, channel } = interaction;

      if (!guild) {
        await interaction.followUp({ content: 'Não foi possível detectar o servidor.', flags: [MessageFlags.Ephemeral] });
        return;
      }

      if (!channel || !channel.isTextBased()) {
        await interaction.followUp({ content: 'Use este comando em um canal de texto.', flags: [MessageFlags.Ephemeral] });
        return;
      }

      const questInput = interaction.options.getString('missao', true);
      const quest = await resolveQuestFromInput(questInput);

      if (!quest) {
        await interaction.followUp({
          content: 'Missão não localizada. Selecione pelo autocomplete.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const requesterIsQuestMaster = user.id === quest.questMaster;
      const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
      const requesterIsAdminOrMod =
        memberRoles.includes(bonfireRoles.adminRoleName) ||
        memberRoles.includes(bonfireRoles.moderatorRoleName) ||
        hasBotAdminPermission(user.id, interaction.member);

      if (!requesterIsQuestMaster && !requesterIsAdminOrMod) {
        await interaction.followUp({
          content: 'Apenas o mestre da missão ou a Staff podem atualizar os ranks.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const ranksString = interaction.options.getString('novos_ranks', true);
      const extractedRoleIds = ranksString.match(/<@&!?(\d+)>/g)?.map((m) => m.replace(/<@&!?/, '').replace('>', '')) || [];

      const validRoleIds: string[] = [];
      const guildRoles = await guild.roles.fetch();

      for (const roleId of extractedRoleIds) {
        if (guildRoles.has(roleId)) {
          validRoleIds.push(roleId);
        }
      }

      if (validRoleIds.length === 0) {
        await interaction.followUp({
          content: 'Nenhum cargo válido mencionado. Você precisa mencionar o cargo do rank (ex: `@Ametista`).',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      quest.allowedRanks = validRoleIds;

      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
      const updatedQuest = await updateQuestUseCase.execute(quest);

      const mentions = validRoleIds.map((id) => `<@&${id}>`).join(' ');

      if (updatedQuest.isPublished) {
        const textChannel = channel as TextChannel;
        await textChannel.send({
          content: `Vagas da missão **${updatedQuest.name}** atualizadas para os ranks: ${mentions}`,
        });
      }

      await interaction.followUp({
        content: `Os ranks da missão foram atualizados com sucesso. Cargos adicionados: ${mentions}`,
        flags: [MessageFlags.Ephemeral],
      });
    } catch (error) {
      bot.logger.log('error', 'Erro no comando missao-atualizar-rank', error);
      await interaction.followUp({
        content: `Erro ao atualizar rank: ${error}`,
        flags: [MessageFlags.Ephemeral],
      });
    }
  },
};

export default updateQuestRankCommand;
