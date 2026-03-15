# Plan aplicado: Alinear plataforma del terreno con la costa (diagonal lineal)
Fecha: 2026-02-24
Estado: APLICADO — commit de referencia visual en .playwright-mcp/coast-align-overview.png

## Resumen
Se reemplazó el borde norte rectangular (zMarS=0.61 uniforme) de buildUnifiedPlatform
con un borde DIAGONAL que interpola linealmente entre los dos centinelas de COAST_POINTS:
- zCoastW = 0.4147  (oeste, xL=-7.2)
- zCoastE = 1.4668  (este,  xR=+7.2)
- zNorthAt(x) = zCoastW + (zCoastE - zCoastW) * (x - xL) / (xR - xL)

## Cambios en app/static/js/asturias-scene.js

### 1. Constantes y funciones auxiliares (tras surfaceY, ~línea 3419)
```js
const zCoastW = 0.4147;
const zCoastE = 1.4668;
function zNorthAt(x) { return zCoastW + (zCoastE - zCoastW) * (x - xL) / (xR - xL); }
function surfaceYatN(z, zN) {
  if (z <= zS)  return Y_top;
  if (z >= zN)  return Y_mar;
  return Y_top * (1 - (z - zS) / (zN - zS));
}
```

### 2. getTerrainY usa surfaceYatN(wz, zNorthAt(wx))

### 3. buildSideWall(x, zN) — límite norte variable
- buildSideWall(xL, zCoastW)  // oeste: termina en Z=0.41
- buildSideWall(xR, zCoastE)  // este:  termina en Z=1.47

### 4. Pared norte: 30 quads diagonales en lugar de 1 rectangular

### 5. Base: quad(xL,yB,zS, xR,yB,zS, xR,yB,zCoastE, xL,yB,zCoastW, mBase)

### 6. Pared vidrio OESTE: zMarS → zCoastW

### 7. Pared vidrio ESTE: zMarS → zCoastE

### 8. Arena: BufferGeometry diagonal (borde sur sigue zNorthAt)

### 9. Malla terreno: bucle ix-exterior/iz-interior con zNorthAt(wx)
- vertex(ix,iz) = ix*(segZ+1)+iz

### 10. Árbol [6.4, 0.42, 0.85, 2] eliminado

## Para DESHACER
Revertir todos los cambios anteriores:
- Restaurar surfaceY() como único helper de altura
- Restaurar buildSideWall(x) sin parámetro zN, usando zMarS
- Restaurar pared norte: quad(xL,Y_mar,zMarS, xR,Y_mar,zMarS, xR,yB,zMarS, xL,yB,zMarS, mSeaWall)
- Restaurar base: quad(xL,yB,zS, xR,yB,zS, xR,yB,zMarS, xL,yB,zMarS, mBase)
- Restaurar paredes vidrio con zMarS
- Restaurar arena: PlaneGeometry centrada en zMarS + (zMarN-zMarS)/2
- Restaurar bucle terreno: iz-exterior/ix-interior con wz=zS+(zMarS-zS)*(iz/segZ)
- Restaurar árbol [6.4, 0.42, 0.85, 2]
