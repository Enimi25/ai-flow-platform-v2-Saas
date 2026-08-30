import path from "node:path";

/**
 * Where mutable state lives.
 *
 * Every store in here is a JSON file. Written next to the code they vanish on
 * each deploy, which on Render meant connected social accounts and the whole
 * post queue disappearing the moment anything shipped. DATA_DIR points at a
 * mounted disk in production; locally it stays in the repo as before.
 *
 * The join always runs down to the file name. Producing a bare directory path
 * here makes Turbopack treat it as a directory to walk, and it then chokes on
 * the broken symlink under work/live-source/venv.
 */
export function dataFile(name: string) {
  const root = process.env.DATA_DIR;
  return root ? path.join(root, name) : path.join(process.cwd(), ".data", name);
}
