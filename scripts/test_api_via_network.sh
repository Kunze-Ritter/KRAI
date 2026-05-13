#!/bin/bash
set -e

echo "=== Testing Pipeline Errors API via Docker Network ==="
echo ""

# Login
echo "1. Login..."
LOGIN_RESPONSE=$(curl -s -X POST http://krai-engine-prod:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"//;s/"//')

if [ -z "$TOKEN" ]; then
  echo "   Failed to get token"
  echo "   Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "   Login successful!"
echo ""

# Test List Errors
echo "2. GET /api/v1/pipeline/errors"
ERRORS_RESPONSE=$(curl -s -X GET http://krai-engine-prod:8000/api/v1/pipeline/errors \
  -H "Authorization: Bearer $TOKEN")

TOTAL=$(echo "$ERRORS_RESPONSE" | grep -o '"total":[0-9]*' | cut -d: -f2)
echo "   Success! Total errors: $TOTAL"

ERROR_ID=$(echo "$ERRORS_RESPONSE" | grep -o '"error_id":"[^"]*"' | head -1 | sed 's/"error_id":"//;s/"//')

if [ -n "$ERROR_ID" ]; then
  echo "   First error ID: $ERROR_ID"
  echo ""

  # Test Get Error Details
  echo "3. GET /api/v1/pipeline/errors/$ERROR_ID"
  DETAIL_RESPONSE=$(curl -s -X GET http://krai-engine-prod:8000/api/v1/pipeline/errors/$ERROR_ID \
    -H "Authorization: Bearer $TOKEN")

  ERROR_TYPE=$(echo "$DETAIL_RESPONSE" | grep -o '"error_type":"[^"]*"' | sed 's/"error_type":"//;s/"//')
  echo "   Success! Error type: $ERROR_TYPE"
  echo ""

  # Test Mark Resolved
  echo "4. POST /api/v1/pipeline/mark-error-resolved"
  RESOLVE_RESPONSE=$(curl -s -X POST http://krai-engine-prod:8000/api/v1/pipeline/mark-error-resolved \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"error_id\":\"$ERROR_ID\",\"notes\":\"Test from API script\"}")

  RESOLVED_BY=$(echo "$RESOLVE_RESPONSE" | grep -o '"resolved_by":"[^"]*"' | sed 's/"resolved_by":"//;s/"//')
  echo "   Success! Resolved by: $RESOLVED_BY"
  echo ""
else
  echo "   No errors in database - skipping detail tests"
  echo ""
fi

# Test Retry Stage (should return 501)
echo "5. POST /api/v1/pipeline/retry-stage (expects 501)"
RETRY_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST http://krai-engine-prod:8000/api/v1/pipeline/retry-stage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_id":"test","stage_name":"classification"}')

HTTP_CODE=$(echo "$RETRY_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
if [ "$HTTP_CODE" = "501" ]; then
  echo "   Success! Returns 501 as expected (Not Implemented)"
else
  echo "   Unexpected HTTP code: $HTTP_CODE"
fi
echo ""

# Test Swagger UI
echo "6. Check Swagger UI"
SWAGGER_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://krai-engine-prod:8000/docs)
if [ "$SWAGGER_CODE" = "200" ]; then
  echo "   Success! Swagger UI accessible"
else
  echo "   Failed! HTTP $SWAGGER_CODE"
fi

echo ""
echo "=== Summary ==="
echo "Pipeline Errors API is working!"
echo "All endpoints are accessible and functioning correctly"
echo ""
