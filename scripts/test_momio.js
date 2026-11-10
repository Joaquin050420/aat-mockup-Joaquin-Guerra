// Prueba los 5 casos de la especificación contra la función real de index.html
const fs = require("fs");
const html = fs.readFileSync(__dirname + "/../index.html", "utf8");
const m = html.match(/function probImplicita[\s\S]*?\n}\n/);
const probImplicita = new Function(m[0] + "; return probImplicita;")();
const casos = [[-150, "60.0 %"], [150, "40.0 %"], [-110, "52.4 %"], [130, "43.5 %"], ["", null], [0, null], ["abc", null]];
let fallos = 0;
for (const [input, esperado] of casos) {
  const real = probImplicita(input);
  const ok = real === esperado;
  if (!ok) fallos++;
  console.log(`${ok ? "OK  " : "FALLA"} input=${JSON.stringify(input)} esperado=${esperado} real=${real}`);
}
process.exit(fallos ? 1 : 0);
