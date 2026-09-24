export const passwordRules = [
  {
    label: "At least 8 characters",
    test: (value: string) => value.length >= 8,
  },
  {
    label: "One uppercase letter",
    test: (value: string) => /[A-Z]/.test(value),
  },
  {
    label: "One lowercase letter",
    test: (value: string) => /[a-z]/.test(value),
  },
  { label: "One number", test: (value: string) => /[0-9]/.test(value) },
  {
    label: "One special character",
    test: (value: string) =>
      /[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]/.test(value),
  },
];

export function validatePassword(password: string, confirmation: string) {
  if (!passwordRules.every((rule) => rule.test(password)))
    throw new Error(
      "Use at least 8 characters, including uppercase and lowercase letters, a number, and a special character.",
    );
  if (password !== confirmation) throw new Error("Passwords do not match.");
}
