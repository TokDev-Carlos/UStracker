const SLOT_RE=/^[a-z][a-z0-9_.-]+$/;
const SAFE_ASSET_RE=/^\/assets\/icons\/[a-zA-Z0-9_./-]+\.(png|svg|webp)$/;

let activeSet={name:'none',icons:{}};

export function validateIconSet(candidate){
  if(!candidate||typeof candidate!=='object')throw new Error('Icon set inválido');
  if(typeof candidate.name!=='string'||!candidate.name.trim())throw new Error('Icon set sem nome');
  if(!candidate.icons||typeof candidate.icons!=='object')throw new Error('Icon set sem mapa icons');
  for(const [slot,path] of Object.entries(candidate.icons)){
    if(!SLOT_RE.test(slot))throw new Error(`Slot de ícone inválido: ${slot}`);
    if(path!==null&&path!==''&&(!SAFE_ASSET_RE.test(path)))throw new Error(`Asset de ícone inseguro: ${path}`);
  }
  return candidate;
}

export function setIconSet(candidate){
  activeSet=validateIconSet(candidate);
  return activeSet;
}

export function getIconPath(slot){
  return activeSet.icons?.[slot]||'';
}

export function iconImg(slot,{className='action-icon',alt='',title=''}={}){
  const src=getIconPath(slot);
  if(!src)return '';
  const safeClass=String(className).replace(/[^a-zA-Z0-9 _-]/g,'');
  const escape=s=>String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  return `<img class="${safeClass}" src="${escape(src)}" alt="${escape(alt)}"${title?` title="${escape(title)}"`:''}>`;
}

export async function loadIconSet(url='/assets/icons/icon-set.json'){
  try{
    const response=await fetch(url,{cache:'no-store'});
    if(!response.ok)return activeSet;
    return setIconSet(await response.json());
  }catch{
    return activeSet;
  }
}
