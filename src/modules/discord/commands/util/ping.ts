import { SlashCommandBuilder } from '@discordjs/builders';
import { IDiscordCommand } from '@/modules/discord/types';

const commandData = new SlashCommandBuilder()
  .setName('ping')
  .setDescription('🏓 Responde ping para comandos do bot');

const command: IDiscordCommand = {
  commandData,
  cooldown: 5000,
  allowedRoles: [],
  async execute(bot, interaction) {
    await interaction.reply({ content: 'Pong!', ephemeral: false });
  },
};

export default command;
