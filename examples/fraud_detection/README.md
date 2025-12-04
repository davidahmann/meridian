# Fraud Detection Example

This example demonstrates how to build a simple fraud detection system using Meridian.
It defines features for both `User` and `Merchant` entities and combines them to calculate a transaction risk score.

## Files

- `main.py`: A standalone script that defines features, simulates materialization, and runs a fraud check logic.
- `features.py`: The feature definitions extracted for use with `meridian serve`.

## Running the Standalone Script

```bash
python examples/fraud_detection/main.py
```

## Running the API Server

1. Start the server:
   ```bash
   meridian serve examples/fraud_detection/features.py
   ```

2. Query User Features:
   ```bash
   curl -X POST http://localhost:8000/features \
     -H "Content-Type: application/json" \
     -d '{"entity_name": "User", "entity_id": "u123", "features": ["user_transaction_count_1h", "user_avg_transaction_amount_7d"]}'
   ```

3. Query Merchant Features:
   ```bash
   curl -X POST http://localhost:8000/features \
     -H "Content-Type: application/json" \
     -d '{"entity_name": "Merchant", "entity_id": "m999", "features": ["merchant_risk_score"]}'
   ```
