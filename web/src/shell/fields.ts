// Holding a page's change types to the fields it says it sends. Each plugin's data.ts lists them
// (SENDS), its test holds each list to the writer's fields.json, and Covered holds each change type
// to its list, so a field the writer does not take fails the build or the tests.

/** Every key of T, of each member when T is a union. */
type Keys<T> = T extends unknown ? keyof T : never;

/** true when every key T can send is in List. Otherwise it names the keys missing, and
 * `true satisfies Covered<...>` fails to compile. */
export type Covered<T, List extends readonly string[]> = [Exclude<Keys<T>, List[number]>] extends [never]
  ? true
  : { notInSends: Exclude<Keys<T>, List[number]> };
