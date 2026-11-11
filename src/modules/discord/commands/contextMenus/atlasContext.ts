import { ContextMenuCommandBuilder } from '@discordjs/builders';
import {
  ChannelType,
  ComponentType,
  GuildMember,
  TextChannel,
} from 'discord.js';

import { IDiscordContextMenu, DiscordApplicationCommandTypes } from '@/modules/discord/types';
import {
  canViewChannel,
  sortChannels,
  isTicketChannel,
  isCollapsedCategory,
  formatChannel,
  paginateSections,
  createAtlasEmbed,
  createPaginationRow,
} from '@/modules/discord/commands/bonfire/atlas';

const commandData = new ContextMenuCommandBuilder()
  .setName('Ver Atlas')
  .setType(DiscordApplicationCommandTypes.USER_CONTEXT);

const command: IDiscordContextMenu = {
  commandData,
  cooldown: 5000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      const { guild, member } = interaction;
      if (!guild || !member) {
        await interaction.editReply({ content: 'Não foi possível detectar o servidor.' });
        return;
      }

      const botSpamChannel = guild.channels.cache.find(c => c.name === '🎶┃bot-spam' || c.name.includes('bot-spam')) as TextChannel;
      if (!botSpamChannel) {
        await interaction.editReply({ content: 'Canal 🎶┃bot-spam não encontrado.' });
        return;
      }

      await guild.channels.fetch();

      const guildMember = member as GuildMember;
      const channels = [...guild.channels.cache.values()];
      const categories = channels
        .filter((channel) => channel.type === ChannelType.GuildCategory)
        .sort(sortChannels);

      const sections: string[][] = [];

      for (const category of categories) {
        const visibleChildren = channels
          .filter((channel) => channel.parentId === category.id)
          .filter((channel) => channel.type !== ChannelType.GuildCategory)
          .filter((channel) => canViewChannel(guildMember, channel))
          .sort(sortChannels);
        
        const visibleTicketChildren = visibleChildren.filter((channel) => isTicketChannel(channel.name));
        const visibleRegularChildren = visibleChildren.filter((channel) => !isTicketChannel(channel.name));

        const canViewCategory = canViewChannel(guildMember, category);
        if (!canViewCategory && visibleChildren.length === 0) {
          continue;
        }

        const sectionLines = [`**${category.name}**`];
        const shouldCollapseCategory = isCollapsedCategory(category.name);

        if (shouldCollapseCategory) {
          sectionLines.push(`- Categoria recolhida (${visibleChildren.length} canais)`);
        } else if (visibleRegularChildren.length === 0) {
          sectionLines.push('- Sem canais visíveis');
        } else {
          visibleRegularChildren.forEach((channel) => {
            sectionLines.push(`- ${formatChannel(channel)}`);
          });
        }

        if (visibleTicketChildren.length > 0) {
          sectionLines.push(`- Tickets recolhidos (${visibleTicketChildren.length})`);
        }

        sections.push(sectionLines);
      }

      const uncategorizedChannels = channels
        .filter((channel) => !channel.parentId)
        .filter((channel) => channel.type !== ChannelType.GuildCategory)
        .filter((channel) => canViewChannel(guildMember, channel))
        .sort(sortChannels);

      if (uncategorizedChannels.length > 0) {
        const uncategorizedTickets = uncategorizedChannels.filter((channel) => isTicketChannel(channel.name));
        const uncategorizedRegularChannels = uncategorizedChannels.filter((channel) => !isTicketChannel(channel.name));
        const uncategorizedLines = [
          '**Sem categoria**',
          ...uncategorizedRegularChannels.map((channel) => `- ${formatChannel(channel)}`),
        ];

        if (uncategorizedTickets.length > 0) {
          uncategorizedLines.push(`- Tickets recolhidos (${uncategorizedTickets.length})`);
        }

        if (uncategorizedLines.length > 1) {
          sections.push(uncategorizedLines);
        }
      }

      if (sections.length === 0) {
        await interaction.editReply({ content: 'Nenhum canal visível encontrado.' });
        return;
      }

      const pages = paginateSections(sections);
      let currentPage = 0;

      const renderPage = () => ({
        content: `<@${interaction.user.id}> aqui está o atlas que você solicitou!`,
        embeds: [createAtlasEmbed(pages[currentPage], currentPage, pages.length)],
        components: pages.length > 1 ? [createPaginationRow(currentPage, pages.length)] : [],
      });

      const atlasMessage = await botSpamChannel.send(renderPage());
      
      await interaction.editReply({ content: `O atlas foi gerado com sucesso no canal <#${botSpamChannel.id}>!` });

      if (pages.length <= 1) {
        return;
      }

      const collector = atlasMessage.createMessageComponentCollector({
        componentType: ComponentType.Button,
        time: 5 * 60 * 1000,
      });

      collector.on('collect', async (buttonInteraction) => {
        if (buttonInteraction.user.id !== interaction.user.id) {
          await buttonInteraction.reply({
            content: 'Esse atlas pertence a outro usuário.',
            ephemeral: true,
          });
          return;
        }

        if (buttonInteraction.customId === 'atlas_previous') {
          currentPage = currentPage === 0 ? pages.length - 1 : currentPage - 1;
        }

        if (buttonInteraction.customId === 'atlas_next') {
          currentPage = currentPage === pages.length - 1 ? 0 : currentPage + 1;
        }

        await buttonInteraction.update(renderPage());
      });

      collector.on('end', async () => {
        await atlasMessage.edit({
          content: `<@${interaction.user.id}> o seu atlas expirou.`,
          embeds: [createAtlasEmbed(pages[currentPage], currentPage, pages.length)],
          components: [],
        }).catch(() => null);
      });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
      await interaction.editReply({ content: 'Erro ao gerar o atlas do servidor.' }).catch(() => null);
    }
  },
};

export default command;
