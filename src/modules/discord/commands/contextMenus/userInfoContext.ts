import { EmbedBuilder } from 'discord.js';
import { ContextMenuCommandBuilder } from '@discordjs/builders';
import ptBR, { format } from 'date-fns';

import { IDiscordContextMenu, DiscordApplicationCommandTypes } from '@/modules/discord/types';
import { Colors } from '@/config/discord';

const commandData = new ContextMenuCommandBuilder()
  .setName('User Info')
  .setType(DiscordApplicationCommandTypes.USER_CONTEXT);

const command: IDiscordContextMenu = {
  commandData,
  cooldown: 5 * 1000,
  async execute(bot, interaction) {
    try {
      const user = interaction.targetUser;

      const embedserver = new EmbedBuilder()
        .setColor('Random')
        .setAuthor({ name: '👀 User Info 👀' })
        .setThumbnail(`${user.avatarURL()}`)
        .addFields([{ name: 'ID', value: `${user.id}` }])
        .addFields([{ name: 'USERNAME', value: `${user.username}` }])
        .addFields([{ name: 'TAG', value: `${user.tag}` }])
        .addFields([{
          name: 'CADASTRADO EM',
          value: format(user.createdAt, 'dd/MM/yyyy H:mm:ss', {
            locale: ptBR,
          }),
        }])
        // .addFields([{ name: 'ROLES', value: `${}` }])
        // .addFields([{ name: 'AVATAR URL', value: `[link](${user.avatarURL()})` }])
        .addFields([{
          name: 'AVATAR URL',
          value: `[PNG](${user.displayAvatarURL({
            format: 'png',
            size: 1024,
          })}) | [JPG](${user.displayAvatarURL({
            format: 'jpg',
            size: 1024,
          })}) | [GIF](${user.displayAvatarURL({
            format: 'gif',
            size: 1024,
          })}) | [WEBP](${user.displayAvatarURL({
            format: 'webp',
            size: 1024,
          })})`,
        }])
        // .setImage(user.displayAvatarURL({ format: 'png', size: 512 }))
        .setTimestamp();

      await interaction.reply({
        embeds: [embedserver],
        ephemeral: true,
      });
    } catch (error) {
      bot.logger.log('error', `Erro no ContextMenu ${commandData.name}`, error);
    }
  },
};

export default command;
