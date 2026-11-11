import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { bonfireRoles } from '@/config/bonfire';
import { parseBrazilDateTime } from '@/shared/util/dateTime';
import { hasBotAdminPermission } from '@/modules/discord/util';
import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { questInfoEmbedMessage } from '@/modules/discord/commands/bonfire/rpg/quests/questEmbeds';

const objectIdRegex = /^(?:[a-f\d]{24}|c[a-z0-9]{24})$/i;

const updateQuestTimeCommandData = new SlashCommandBuilder()
  .setName('editar-missao')
  .setDescription('Edita a data e hora de um evento de tempo da missão')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missão').setAutocomplete(true).setRequired(true),
  )
  .addStringOption((option) =>
    option
      .setName('evento')
      .setDescription('Qual evento deseja alterar?')
      .addChoices(
        { name: 'Último Evento', value: 'last' },
        { name: 'Início (Run)', value: 'run' },
        { name: 'Pause', value: 'pause' },
        { name: 'Congelamento (Freeze)', value: 'freeze' },
        { name: 'Finalização (Finish)', value: 'finish' },
      )
      .setRequired(true),
  )
  .addStringOption((option) =>
    option
      .setName('data')
      .setDescription('Nova data no formato DD/MM/AAAA')
      .setRequired(true),
  )
  .addStringOption((option) =>
    option
      .setName('hora')
      .setDescription('Nova hora no formato HH:MM ou HH:MM:SS')
      .setRequired(true),
  )
  .addIntegerOption((option) =>
    option
      .setName('numero')
      .setDescription('Opcional: 1 = primeiro desse tipo, 2 = segundo; vazio = último')
      .setMinValue(1)
      .setRequired(false),
  );

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

const command: IDiscordCommand = {
  commandData: updateQuestTimeCommandData,
  allowedRoles: [
    bonfireRoles.adminRoleName,
    bonfireRoles.moderatorRoleName,
  ],
  cooldown: 3 * 1000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      const questInput = interaction.options.getString('missao', true);
      const eventoOption = interaction.options.getString('evento', true);
      const occurrenceNumber = interaction.options.getInteger('numero');
      const dataOption = interaction.options.getString('data', true);
      const horaOption = interaction.options.getString('hora', true);

      // Validate date and time formats
      if (!/^\d{2}\/\d{2}\/\d{4}$/.test(dataOption)) {
        await interaction.followUp({ content: 'Formato de data inválido. Use DD/MM/AAAA.' });
        return;
      }
      if (!/^\d{2}:\d{2}(:\d{2})?$/.test(horaOption)) {
        await interaction.followUp({ content: 'Formato de hora inválido. Use HH:MM ou HH:MM:SS.' });
        return;
      }

      const quest = await resolveQuestFromInput(questInput);

      if (!quest) {
        await interaction.followUp({
          content: 'Missão não localizada. Selecione pelo autocomplete.',
        });
        return;
      }

      const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
      const requesterIsAdminOrMod =
        memberRoles.includes(bonfireRoles.adminRoleName) ||
        memberRoles.includes(bonfireRoles.moderatorRoleName) ||
        hasBotAdminPermission(interaction.user.id, interaction.member);

      if (!requesterIsAdminOrMod) {
        await interaction.followUp({ content: 'Apenas Admin/Mod pode alterar o tempo da missão.' });
        return;
      }

      if (!quest.timeEvents || quest.timeEvents.length === 0) {
        await interaction.followUp({ content: 'A missão ainda não possui eventos de tempo registrados.' });
        return;
      }

      let eventIndex = -1;

      if (eventoOption === 'last') {
        eventIndex = quest.timeEvents.length - 1;
      } else {
        const matchingEvents = quest.timeEvents
          .map((event, index) => ({ event, index }))
          .filter(({ event }) => event.eventType === eventoOption);

        if (occurrenceNumber) {
          eventIndex = matchingEvents[occurrenceNumber - 1]?.index ?? -1;
        } else {
          eventIndex = matchingEvents[matchingEvents.length - 1]?.index ?? -1;
        }
      }

      if (eventIndex === -1) {
        const occurrenceHint = occurrenceNumber ? ` na posição ${occurrenceNumber}` : '';
        await interaction.followUp({ content: `Nenhum evento do tipo selecionado${occurrenceHint} foi encontrado no histórico da missão.` });
        return;
      }

      const eventTypeNames: Record<string, string> = {
        run: 'Início',
        pause: 'Pause',
        freeze: 'Congelamento',
        finish: 'Finalização'
      };

      const eventToEdit = quest.timeEvents[eventIndex];
      const eventName = eventTypeNames[eventToEdit.eventType] || eventToEdit.eventType;
      const sameTypeEventsBefore = quest.timeEvents
        .slice(0, eventIndex + 1)
        .filter((event) => event.eventType === eventToEdit.eventType)
        .length;

      const newDate = parseBrazilDateTime(dataOption, horaOption);
      
      if (Number.isNaN(newDate.getTime())) {
         await interaction.followUp({ content: 'Data/Hora resultaram em uma data inválida.' });
         return;
      }

      quest.timeEvents[eventIndex].date = newDate;

      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
      await updateQuestUseCase.execute(quest);

      await interaction.followUp({
        content: `✅ O evento **${eventName} #${sameTypeEventsBefore}** foi alterado para **${dataOption} ${horaOption}**.`,
      });

    } catch (error) {
      bot.logger.log('error', `Erro no comando editar-missao`, error);
      await interaction.followUp({
        content: `Não foi possível alterar o tempo da missão:\n${error}`,
      }).catch(() => null);
    }
  },
};

export default command;
