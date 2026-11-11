import { Routes } from 'discord-api-types/v9';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { discordApi } from '@/shared/services/discordApi';

interface IRequest {
  discordClientId: string;
  discordGuildId: string;
}

export class DeleteApplicationGuildCommandsUseCase implements IBaseUseCase {
  public async execute({ discordClientId, discordGuildId }: IRequest): Promise<void> {
    await discordApi.put(Routes.applicationGuildCommands(discordClientId, discordGuildId), {
      body: [],
    });
  }
}
