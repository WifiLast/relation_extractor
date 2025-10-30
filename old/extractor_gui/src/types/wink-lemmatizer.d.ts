declare module 'wink-lemmatizer' {
  /**
   * Lemmatizes a noun to its base form
   * @param word The noun to lemmatize
   * @returns The lemmatized noun
   */
  export function noun(word: string): string;
  
  /**
   * Lemmatizes a verb to its base form
   * @param word The verb to lemmatize
   * @returns The lemmatized verb
   */
  export function verb(word: string): string;
  
  /**
   * Lemmatizes an adjective to its base form
   * @param word The adjective to lemmatize
   * @returns The lemmatized adjective
   */
  export function adjective(word: string): string;
} 