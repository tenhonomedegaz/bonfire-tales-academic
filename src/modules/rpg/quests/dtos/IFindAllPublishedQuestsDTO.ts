export interface IFindAllPublishedQuestsDTO {
  searchTerm: string;
  questStatus?: string[];
  questDateAfter?: Date;
  questDateBefore?: Date;
  options?: { limit?: number };
}
