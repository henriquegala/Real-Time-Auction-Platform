-- bid.lua — atomic bid check-and-set
-- KEYS[1] = auction:{id}:current
-- KEYS[2] = auction:{id}:leader
-- KEYS[3] = auction:{id}:ends_at
-- KEYS[4] = auction:{id}:closed
-- ARGV[1] = new_amount (string, parsed as number)
-- ARGV[2] = bidder_id (string)
-- ARGV[3] = now_iso  (string, ISO-8601 UTC)
--
-- Returns:
--   {"ok", <accepted_amount_str>}        on success
--   {"err", "too_low"}                   if amount <= current
--   {"err", "closed"}                    if auction ended or marked closed
--   {"err", "missing"}                   if auction not initialized

local current_s = redis.call("GET", KEYS[1])
local ends_at   = redis.call("GET", KEYS[3])
local closed    = redis.call("GET", KEYS[4])

if not current_s or not ends_at then
  return {"err", "missing"}
end

if closed == "1" then
  return {"err", "closed"}
end

-- string compare on ISO-8601 UTC timestamps is monotonic
if ARGV[3] >= ends_at then
  return {"err", "closed"}
end

local current = tonumber(current_s)
local new_amt = tonumber(ARGV[1])

if not new_amt or new_amt <= current then
  return {"err", "too_low"}
end

redis.call("SET", KEYS[1], ARGV[1])
redis.call("SET", KEYS[2], ARGV[2])
return {"ok", ARGV[1]}
