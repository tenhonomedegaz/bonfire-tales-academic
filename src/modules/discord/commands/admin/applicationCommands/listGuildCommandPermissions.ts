import { SlashCommandBuilder } from '@discordjs/builders';
import {
  IDiscordCommand,
  IDiscordContextMenu,
  DiscordApplicationCommandTypes,
} from '@/modules/discord/types';
import { botRootAdminRoleName } from '@/config/discord';
import { commands } from '@/modules/discord/commands';
import { contextMenus } from '@/modules/discord/commands/contextMenus';

// Categorization helper
function categorizeCommand(commandName: string): string {
  if (commandName.startsWith('moderador')) return '👮 Administração';
  if (commandName.startsWith('mensagens')) return '🗑️ Mensagens';
  if (commandName.startsWith('missao')) return '🗺️ Missões';
  if (commandName.startsWith('token')) return '🎟️ Tokens';
  if (commandName.startsWith('colab')) return '🤝 Colaboradores';
  if (commandName.startsWith('baixa')) return '⏳ Baixa Prioridade';
  if (commandName.startsWith('item')) return '📦 Itens';
  if (commandName.startsWith('pagamento')) return '💳 Pagamentos';

  // Bonfire modules
  if (commandName.startsWith('rpg')) return '🎲 Bonfire RPG';
  if (commandName.startsWith('sub')) return '🔥 Bonfire Subscriptions';

  return '📂 Outros';
}

// Split very long messages into chunks
function splitMessage(text: string, maxLength = 1900): string[] {
  const chunks: string[] = [];
  let current = '';

  for (const line of text.split('\n')) {
    if ((current + '\n' + line).length > maxLength) {
      chunks.push(current);
      current = line;
    } else {
      current += (current.length === 0 ? '' : '\n') + line;
    }
  }

  if (current.length > 0) chunks.push(current);
  return chunks;
}

const commandData = new SlashCommandBuilder()
  .setName('comandos-listar')
  .setDescription('📜 Lista todos os comandos com categorias e permissões');

const command: IDiscordCommand = {
  commandData,
  cooldown: 3 * 1000,
  allowedRoles: [],

  async execute(bot, interaction) {
    try {
      await interaction.reply({
        content: '📡 Gerando lista de comandos...',
        ephemeral: true,
      });

      const categorized: Record<string, string[]> = {};

      // Build slash command list
      commands.forEach((cmd) => {
        const name = cmd.commandData?.name;
        if (!name) return;

        const description = cmd.commandData?.description ?? 'Sem descrição';
        const cooldown = cmd.cooldown ? `${cmd.cooldown / 1000}s` : 'Nenhum';
        const roles = cmd.allowedRoles
          ? cmd.allowedRoles.map((r) => `@${r}`).join(', ')
          : 'Todos';

        const category = categorizeCommand(name);
        if (!categorized[category]) categorized[category] = [];

        categorized[category].push(
          `• **/${name}** — *${description}*\n` +
            `   ↳ ⏱ **${cooldown}** | 🔐 **${roles}**`
        );
      });

      // Build context menu list
      const contextLines: string[] = [];
      contextMenus.forEach((menu: IDiscordContextMenu) => {
        const name = menu.commandData?.name;
        const type =
          menu.commandData?.type === DiscordApplicationCommandTypes.USER_CONTEXT
            ? 'User Context'
            : menu.commandData?.type === DiscordApplicationCommandTypes.MESSAGE_CONTEXT
            ? 'Message Context'
            : 'Context Menu';

        const cooldown = menu.cooldown ? `${menu.cooldown / 1000}s` : 'Nenhum';
        const roles = menu.allowedRoles
          ? menu.allowedRoles.map((r) => `@${r}`).join(', ')
          : 'Todos';

        contextLines.push(
          `• **${name}** — *${type}*\n` +
            `   ↳ ⏱ **${cooldown}** | 🔐 **${roles}**`
        );
      });

      // Build the full raw message
      let full = `# 📜 Lista de Comandos do Servidor\n`;

      for (const category of Object.keys(categorized)) {
        full += `\n## ${category}\n`;
        full += categorized[category].join('\n') + '\n';
      }

      if (contextLines.length > 0) {
        full += `\n## 🖱️ Comandos de Contexto\n`;
        full += contextLines.join('\n') + '\n';
      }

      // Split into multiple safe chunks
      const chunks = splitMessage(full);

      // Send follow-up messages for each chunk
      for (const chunk of chunks) {
        await interaction.followUp({
          content: chunk,
          ephemeral: true,
        });
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
      await interaction.reply({
        content: '❌ Erro ao listar comandos.',
        ephemeral: true,
      });
    }
  },
};

export default command;
