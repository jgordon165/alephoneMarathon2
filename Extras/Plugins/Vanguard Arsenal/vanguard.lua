--[[
  Vanguard Arsenal - weapon behaviour

  Burst rifle (assault rifle slot)
    Each trigger pull fires exactly 3 rounds, then a short delay before
    the next burst. Holding the trigger keeps firing bursts. A burst that
    has started always finishes, even if the trigger is let go.

  Plasma pistol (fusion pistol slot)
    Every shot adds heat; heat bleeds off shortly after you stop firing.
    At full heat the pistol overheats and vents: it can't fire until the
    vent finishes. A charged shot (hold secondary) overheats it at once.
    Heat keeps cooling while the pistol is holstered.

  Uses only deterministic state, so it is safe for net games and films
  (every player needs the plugin). The HUD readout is drawn for the local
  player only, through overlays, which don't affect the simulation.

  Tuning lives in the constants below and in "Vanguard Arsenal.mml".
]]

-- Burst rifle
local BURST_ROUNDS = 3
local BURST_DELAY_TICKS = 9          -- ticks between bursts (30 ticks = 1 second)

-- Plasma pistol heat (0-100)
local HEAT_PER_SHOT = 11             -- ~9 rapid shots to overheat
local CHARGED_SHOT_ROUNDS = 4        -- a charged shot drains this many rounds at once
local COOL_DELAY_TICKS = 10          -- cooling starts this long after the last shot
local COOL_PER_TICK = 1.6            -- full heat cools in ~2 seconds
local VENT_TICKS = 75                -- overheated: 2.5 seconds unable to fire
local VENT_SOUND = "spht door opening"

local state = {}

local function player_state(p)
  local s = state[p.index]
  if not s then
    s = {
      burst_mode = "ready",  -- "ready", "bursting" or "delay"
      burst_fired = 0,
      burst_delay = 0,
      rifle_rounds = nil,
      heat = 0,
      vent = 0,
      since_shot = 0,
      pistol_rounds = nil,
      hud = nil,
    }
    state[p.index] = s
  end
  return s
end

local function holding(p, type_name)
  local current = p.weapons.current
  return current ~= nil and current.type == WeaponTypes[type_name]
end

local function update_burst_rifle(p, s)
  if not holding(p, "assault rifle") then
    s.burst_mode = "ready"
    s.rifle_rounds = nil
    return
  end

  local rounds = p.weapons.current.primary.rounds
  local last = s.rifle_rounds or rounds
  s.rifle_rounds = rounds

  if s.burst_mode == "bursting" then
    if rounds < last then
      s.burst_fired = s.burst_fired + (last - rounds)
    end
    -- done after 3 rounds, or if the magazine ran dry or was reloaded
    if s.burst_fired >= BURST_ROUNDS or rounds == 0 or rounds > last then
      s.burst_mode = "delay"
      s.burst_delay = BURST_DELAY_TICKS
      p.action_flags.left_trigger = false
    else
      p.action_flags.left_trigger = true
    end
    return
  end

  if s.burst_mode == "delay" then
    p.action_flags.left_trigger = false
    s.burst_delay = s.burst_delay - 1
    if s.burst_delay <= 0 then
      s.burst_mode = "ready"
    end
    return
  end

  -- ready: a pull with rounds loaded starts a burst; the trigger stays
  -- down this tick, so the first round fires now
  if p.action_flags.left_trigger and rounds > 0 then
    s.burst_mode = "bursting"
    s.burst_fired = 0
  end
end

local function update_plasma_pistol(p, s)
  local held = holding(p, "fusion pistol")
  local rounds = p.weapons[WeaponTypes["fusion pistol"]].primary.rounds
  local last = s.pistol_rounds or rounds
  s.pistol_rounds = rounds

  -- shots fired since last tick (reloads and pickups only add rounds)
  if held and rounds < last and s.vent == 0 then
    local spent = last - rounds
    if spent >= CHARGED_SHOT_ROUNDS then
      s.heat = 100
    else
      s.heat = s.heat + HEAT_PER_SHOT * spent
    end
    s.since_shot = 0
  end

  if s.vent == 0 and s.heat >= 100 then
    s.heat = 100
    s.vent = VENT_TICKS
    if held and p == Players.local_player then
      p:play_sound(VENT_SOUND, 1.3)
    end
  end

  if s.vent > 0 then
    s.vent = s.vent - 1
    s.heat = 100 * s.vent / VENT_TICKS
    if held then
      p.action_flags.left_trigger = false
      p.action_flags.right_trigger = false
    end
  else
    s.since_shot = s.since_shot + 1
    if s.since_shot > COOL_DELAY_TICKS and s.heat > 0 then
      s.heat = math.max(0, s.heat - COOL_PER_TICK)
    end
  end
end

-- Local player's heat gauge in overlay 0.
local function update_hud(p, s)
  if p ~= Players.local_player then return end

  local text, color = nil, nil
  if holding(p, "fusion pistol") then
    local filled = math.floor(s.heat / 10 + 0.5)
    local bar = string.rep("|", filled) .. string.rep(".", 10 - filled)
    if s.vent > 0 then
      text = "PLASMA  [" .. bar .. "]  OVERHEATED - VENTING"
      color = "red"
    else
      text = "PLASMA  [" .. bar .. "]  HEAT " .. math.floor(s.heat) .. "%"
      if s.heat >= 75 then color = "red"
      elseif s.heat >= 45 then color = "yellow"
      else color = "cyan" end
    end
  end

  local key = text and (text .. color) or nil
  if key == s.hud then return end
  s.hud = key
  if text then
    p.overlays[0].text = text
    p.overlays[0].color = color
  else
    p.overlays[0]:clear()
  end
end

Triggers = {}

function Triggers.init(restoring_game)
  state = {}
end

function Triggers.idle()
  for p in Players() do
    local s = player_state(p)
    if p.dead then
      s.burst_mode = "ready"
      s.heat, s.vent = 0, 0
    else
      update_burst_rifle(p, s)
      update_plasma_pistol(p, s)
    end
    update_hud(p, s)
  end
end
