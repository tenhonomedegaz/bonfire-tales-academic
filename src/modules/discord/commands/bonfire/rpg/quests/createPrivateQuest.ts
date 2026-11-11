/* eslint-disable no-restricted-syntax */
import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';
import { ChannelType, TextChannel } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { questInfoEmbedMessage } from './questEmbeds';
import { nowInBrazil } from '@/shared/util/dateTime';


const PRIVATE_QUEST_CATEGORY_NAME = '╭────👑Mesas Privadas';

const commandData = new SlashCommandBuilder()
  .setName('missao-privada-criar')
  .setDescription('Cria uma missão privada simples')
  .addStringOption((option) =>
    option
      .setName('nome-missao')
      .setDescription('Nome da missão')
      .setRequired(true),
  )
  .addUserOption((option) =>
    option
      .setName('jogador')
      .setDescription('Jogador que solicitou a missão')
      .setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.masterRoleName, bonfireRoles.testMasterRoleName],
  cooldown: 3000,

  async execute(bot, interaction) {
    try {
      await interaction.reply({ content: 'Criando missão privada...', ephemeral: true });

      const { user, guild } = interaction;
      if (!guild) {
        await interaction.editReply({ content: 'Não foi possível detectar o servidor.' });
        return;
      }

      const questName = interaction.options.getString('nome-missao', true);
      const requestedBy = interaction.options.getUser('jogador', true);
      const requestedMember = await guild.members.fetch(requestedBy.id).catch(() => null);

      if (!requestedMember || requestedMember.user.bot) {
        await interaction.editReply({ content: `A marcação \`${requestedBy.username}\` não é um usuário válido.` });
        return;
      }

      await guild.channels.fetch();
      const privateCategory = guild.channels.cache.find(
        (guildChannel) =>
          guildChannel.type === ChannelType.GuildCategory &&
          guildChannel.name === PRIVATE_QUEST_CATEGORY_NAME,
      );

      if (!privateCategory) {
        await interaction.editReply({ content: `Categoria \`${PRIVATE_QUEST_CATEGORY_NAME}\` não encontrada.` });
        return;
      }

      const questChannel = await guild.channels.create({
        name: questName.substring(0, 90),
        type: ChannelType.GuildText,
        parent: privateCategory.id,
      });

      const questsRepository = container.resolve<IQuestsRepository>('QuestsRepository');
      const now = nowInBrazil();

      const quest = await questsRepository.create({
        guildId: guild.id,
        channelId: questChannel.id,
        name: questName,
        description: `Missão privada solicitada por <@${requestedBy.id}>.`,
        questDate: now,
        playersAmount: 1,
        rules: 'https://app.roll20.net',
        tags: ['privada'],
        type: 'Privada',
        tableUrl: `https://discord.com/channels/${guild.id}/${questChannel.id}`,
        questMaster: user.id,
        allowedRanks: [],
        highPriorityPlayers: [],
        questPlayers: [{ userId: requestedBy.id, type: 'normal' }],
        createdBy: user.id,
        isPublished: true,
        status: 'idle',
      });

      const questInfoMessage = await questInfoEmbedMessage({ quest, showQueueList: true });

      await (questChannel as TextChannel).send({
        content: `<@${user.id}> <@${requestedBy.id}>`,
        embeds: [questInfoMessage],
      });

      await interaction.followUp({
        content: `Missão privada criada para <@${requestedBy.id}> em <#${questChannel.id}>.`,
        embeds: [questInfoMessage],
        ephemeral: true,
      });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
      await interaction.followUp({
        content: `Erro ao criar missão privada:\n${error}`,
        ephemeral: true,
      }).catch(() => null);
    }
  },
};

export default command;
