import { ColorResolvable } from 'discord.js';

export const botRootAdminRoleName = 'bot-admin';

type ColorsKeys = 'green500' | 'red500' | 'red900' | 'random';

type ColorTypes = {
  [key in ColorsKeys]: ColorResolvable;
};

export const Colors: ColorTypes = {
  green500: '#59c171',
  red500: '#d44059',
  red900: '#9E0000',
  random: 'Random',
};
