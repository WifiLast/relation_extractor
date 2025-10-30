declare module 'lemmatize-en' {
  /**
   * Lemmatizes an English word to its base form
   * @param word The word to lemmatize
   * @returns An array of possible lemmas (base forms) for the word, or empty array if none found
   */
  export function lemmatize(word: string): string[];
} 