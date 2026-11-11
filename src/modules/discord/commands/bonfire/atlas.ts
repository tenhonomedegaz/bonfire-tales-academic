import { SlashCommandBuilder } from '@discordjs/builders';
import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  ChannelType,
  ComponentType,
  EmbedBuilder,
  GuildBasedChannel,
  GuildMember,
  PermissionsBitField,
} from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRpgRankRoles } from '@/config/bonfire';
import { Colors } from '@/config/discord';

const COLLAPSED_CATEGORY_TERMS = [
  'rp privado',
  'roleplay fechado',
  'arco de missão',
  'arcos de missão',
  'mesa privada',
  'mesas privadas',
  'ticket',
  'tickets',
  ...bonfireRpgRankRoles.map((role) => role.name),
];

const commandData = new SlashCommandBuilder()
  .setName('atlas')
  .setDescription('Mostra um mapa dos canais que você consegue acessar')
  .addBooleanOption((option) =>
    option
      .setName('todos-os-canais')
      .setDescription('Lista também os canais dentro de categorias recolhidas')
      .setRequired(false),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],
  cooldown: 5000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      const { guild, member } = interaction;
      if (!guild || !member) {
        await interaction.editReply({ content: 'Não foi possível detectar o servidor.' });
        return;
      }

      await guild.channels.fetch();

      const showAllChannels = interaction.options.getBoolean('todos-os-canais') ?? false;
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
        const visibleRegularChildren = showAllChannels
          ? visibleChildren
          : visibleChildren.filter((channel) => !isTicketChannel(channel.name));

        const canViewCategory = canViewChannel(guildMember, category);
        if (!canViewCategory && visibleChildren.length === 0) {
          continue;
        }

        const sectionLines = [`**${category.name}**`];
        const shouldCollapseCategory = !showAllChannels && isCollapsedCategory(category.name);

        if (shouldCollapseCategory) {
          sectionLines.push(`- Categoria recolhida (${visibleChildren.length} canais)`);
        } else if (visibleRegularChildren.length === 0) {
          sectionLines.push('- Sem canais visíveis');
        } else {
          visibleRegularChildren.forEach((channel) => {
            sectionLines.push(`- ${formatChannel(channel)}`);
          });
        }

        if (!showAllChannels && visibleTicketChildren.length > 0) {
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
        const uncategorizedRegularChannels = showAllChannels
          ? uncategorizedChannels
          : uncategorizedChannels.filter((channel) => !isTicketChannel(channel.name));
        const uncategorizedLines = [
          '**Sem categoria**',
          ...uncategorizedRegularChannels.map((channel) => `- ${formatChannel(channel)}`),
        ];

        if (!showAllChannels && uncategorizedTickets.length > 0) {
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
        embeds: [createAtlasEmbed(pages[currentPage], currentPage, pages.length)],
        components: pages.length > 1 ? [createPaginationRow(currentPage, pages.length)] : [],
      });

      const atlasMessage = await interaction.editReply(renderPage());

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
          embeds: [createAtlasEmbed(pages[currentPage], currentPage, pages.length)],
          components: [],
        }).catch(() => null);
      });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
      await interaction.editReply({ content: 'Erro ao gerar o atlas do servidor.' });
    }
  },
};

export function canViewChannel(member: GuildMember, channel: GuildBasedChannel): boolean {
  return member.permissionsIn(channel).has(PermissionsBitField.Flags.ViewChannel);
}

export function formatChannel(channel: GuildBasedChannel): string {
  const channelMention = `<#${channel.id}>`;

  if (channel.type === ChannelType.GuildVoice || channel.type === ChannelType.GuildStageVoice) {
    return `Voz: ${channelMention}`;
  }

  return channelMention;
}

export function createAtlasEmbed(page: string, pageIndex: number, totalPages: number): EmbedBuilder {
  return new EmbedBuilder()
    .setColor(Colors.green500)
    .setTitle('Atlas do Servidor')
    .setDescription(page)
    .setFooter({ text: `Página ${pageIndex + 1}/${totalPages}` });
}

export function createPaginationRow(pageIndex: number, totalPages: number): ActionRowBuilder<ButtonBuilder> {
  return new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder()
      .setCustomId('atlas_previous')
      .setLabel('Anterior')
      .setStyle(ButtonStyle.Secondary),
    new ButtonBuilder()
      .setCustomId('atlas_next')
      .setLabel('Próxima')
      .setStyle(ButtonStyle.Secondary),
  );
}

export function isCollapsedCategory(categoryName: string): boolean {
  const normalizedName = normalize(categoryName);
  return COLLAPSED_CATEGORY_TERMS.some((term) => normalizedName.includes(normalize(term)));
}

export function normalize(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function sortChannels(a: GuildBasedChannel, b: GuildBasedChannel): number {
  return ((a as any).rawPosition || 0) - ((b as any).rawPosition || 0);
}

export function isTicketChannel(channelName: string): boolean {
  const normalizedName = normalize(channelName);
  return normalizedName.startsWith('ticket-') || /^ticket-\d+$/i.test(channelName);
}

export function paginateSections(sections: string[][], maxLength = 3400): string[] {
  const pages: string[] = [];

  for (const section of sections) {
    const [sectionTitle, ...sectionLines] = section;
    let current = sectionTitle;

    for (const line of sectionLines) {
      const next = `${current}\n${line}`;

      if (next.length > maxLength) {
        pages.push(current);
        current = `${sectionTitle} (continuação)\n${line}`;
      } else {
        current = next;
      }
    }

    pages.push(current);
  }

  return pages;
}

export default command;
