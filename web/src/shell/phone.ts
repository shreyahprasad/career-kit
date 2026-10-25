// The phone, as the layout sees it. Keep in step with the phone block in tokens.css.
const PHONE = "(max-width: 640px)";

/** True on a phone-width screen. Read once, for what a card starts as (folded or open). */
export const isPhone = () => window.matchMedia(PHONE).matches;
