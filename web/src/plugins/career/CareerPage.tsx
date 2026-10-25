import { Board } from "./Board";
import { RolePage } from "./RolePage";

// #/career is the board of every role by status; #/career/<role> is that role.

export function CareerPage({ path }: { path: string[] }) {
  const [roleId] = path;
  return roleId ? <RolePage key={roleId} id={roleId} /> : <Board />;
}
