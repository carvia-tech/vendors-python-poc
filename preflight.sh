#!/usr/bin/env bash
# Egress preflight - run this ON the target server before deploying.
#
# The enrichment pipeline depends on two hosts that block datacenter IPs.
# If either check fails, the app deploys fine but returns empty results:
# company-name search finds nothing and the registry/reviews tabs stay blank.
echo "Egress IP : $(curl -s --max-time 10 https://api.ipify.org || echo UNKNOWN)"

zauba=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \
  https://www.zaubacorp.com/companysearchresults/PROLIFICS)
echo "ZaubaCorp : HTTP $zauba $([ "$zauba" = 200 ] && echo '(OK)' || echo '(BLOCKED - registry tab will be empty)')"

# Follow redirects: /html/ legitimately 302s before serving results, so a
# bare status check reports a false block. What matters is whether real
# result links come back, so grep the body for them.
ddg_body=$(curl -sL --max-time 25 \
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \
  'https://html.duckduckgo.com/html/?q=prolifics')
if echo "$ddg_body" | grep -q 'result__a\|result__snippet'; then
  ddg=200; echo "Web search: results returned (OK)"
else
  ddg=000; echo "Web search: no results in body (BLOCKED - name search and reviews will be empty)"
fi

echo
if [ "$zauba" = 200 ] && [ "$ddg" = 200 ]; then
  echo "VERDICT: safe to deploy - both sources reachable from this host."
else
  echo "VERDICT: deploy will build and run, but return empty data."
  echo "         Swap to licensed search + MCA APIs, or deploy on-prem."
fi
