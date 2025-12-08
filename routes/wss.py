"""WebSocket routes for WakeLink Cloud Server.

This module provides WebSocket endpoints for real-time bidirectional
communication with devices. Implements protocol v1.0 with transparent
relay of outer JSON packets.

The server acts as a blind relay:
- Validates API token from first JSON message (auth message)
- Does NOT decrypt the inner payload
- Forwards outer JSON {device_id, payload, signature, version} as-is

Authentication Protocol:
1. Client connects to /ws/{device_id} or /ws/client/{client_id}
2. Client sends auth message: {"type": "auth", "token": "<api_token>"}
3. Server validates token and sends welcome or error response
4. Normal packet exchange begins

Author: deadboizxc
Version: 1.0
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import validate_api_token, validate_device_token
from core.models import Message, Device
from core.relay import relay

router = APIRouter(tags=["websocket"])
logger = logging.getLogger("wakelink_cloud")

# Authentication timeout in seconds
AUTH_TIMEOUT = 10.0


def _extract_token_from_headers(websocket: WebSocket) -> Optional[str]:
    """Extract API token from WebSocket headers (fallback for backwards compatibility).
    
    Checks:
    1. Authorization header (Bearer token)
    2. X-API-Token header
    
    Args:
        websocket: The WebSocket connection.
        
    Returns:
        The API token string or None if not found.
    """
    auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    
    return websocket.headers.get("x-api-token")


async def _wait_for_auth_message(
    websocket: WebSocket,
    timeout: float = AUTH_TIMEOUT
) -> tuple[bool, Optional[str], Optional[dict]]:
    """Wait for authentication message from client.
    
    Expected auth message format:
    {"type": "auth", "token": "<api_token>"}
    
    Args:
        websocket: The WebSocket connection.
        timeout: Maximum time to wait for auth message.
        
    Returns:
        Tuple of (success, token, first_data_message).
        first_data_message is returned if client sends a data packet instead of auth.
    """
    try:
        raw_data = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=timeout
        )
        
        try:
            message = json.loads(raw_data)
        except json.JSONDecodeError:
            return False, None, None
        
        # Check if this is an auth message
        if message.get("type") == "auth":
            token = message.get("token")
            return True, token, None
        
        # Not an auth message - might be a data packet (legacy client)
        # Return the message so it can be processed after header-based auth
        return False, None, message
        
    except asyncio.TimeoutError:
        return False, None, None
    except Exception:
        return False, None, None


async def _authenticate_websocket_device(
    websocket: WebSocket,
    device_id: str,
    api_token: str
) -> tuple[bool, Optional[object], Optional[object], Session]:
    """Authenticate device WebSocket connection via API token and device_id.
    
    Authentication flow:
    1. Accept WebSocket connection
    2. Validate api_token from Authorization header
    3. Verify that user owns the device
    4. Get device_token from database (for packet encryption)
    5. Send success/error response
    
    Args:
        websocket: The WebSocket connection.
        device_id: The device ID from URL path.
        api_token: The API token from Authorization header.
        
    Returns:
        Tuple of (success, user, device, db_session).
    """
    db = next(get_db())
    await websocket.accept()
    
    # Validate API token (user authentication)
    user = validate_api_token(db, api_token)
    
    if not user:
        await websocket.send_json({
            "status": "error",
            "error": "INVALID_API_TOKEN",
            "message": "Invalid API token"
        })
        await websocket.close(code=1008, reason="Invalid API token")
        return False, None, None, db
    
    # Get device and verify ownership
    device = db.query(Device).filter(
        Device.device_id == device_id,
        Device.user_id == user.id
    ).first()
    
    if not device:
        await websocket.send_json({
            "status": "error",
            "error": "DEVICE_NOT_FOUND",
            "message": f"Device {device_id} not found or not owned by user"
        })
        await websocket.close(code=1008, reason="Device not found")
        return False, None, None, db
    
    return True, user, device, db


async def _authenticate_websocket(
    websocket: WebSocket
) -> tuple[bool, Optional[object], Session, Optional[dict]]:
    """Authenticate WebSocket connection via JSON auth message.
    
    Authentication flow:
    1. Accept WebSocket connection
    2. Wait for auth message: {"type": "auth", "token": "..."}
    3. Validate token
    4. Send success/error response
    
    Also supports legacy header-based authentication for backwards compatibility.
    
    Args:
        websocket: The WebSocket connection.
        
    Returns:
        Tuple of (success, user, db_session, first_data_message).
        first_data_message is non-None if client sent data instead of auth (legacy).
    """
    db = next(get_db())
    await websocket.accept()
    
    # First, try to get token from headers (backwards compatibility)
    header_token = _extract_token_from_headers(websocket)
    
    # Wait for auth message
    auth_received, json_token, first_message = await _wait_for_auth_message(websocket)
    
    # Determine which token to use
    token = None
    if auth_received and json_token:
        # JSON auth takes priority
        token = json_token
        logger.debug("[WSS] Auth via JSON message")
    elif header_token:
        # Fall back to header-based auth (legacy)
        token = header_token
        logger.debug("[WSS] Auth via headers (legacy)")
    
    if not token:
        await websocket.send_json({
            "status": "error",
            "error": "AUTH_REQUIRED",
            "message": "Authentication required. Send: {\"type\": \"auth\", \"token\": \"<api_token>\"}"
        })
        await websocket.close(code=1008)
        return False, None, db, None
    
    user = validate_api_token(db, token)
    if not user:
        await websocket.send_json({
            "status": "error",
            "error": "INVALID_TOKEN",
            "message": "Invalid API token"
        })
        await websocket.close(code=1008)
        return False, None, db, None
    
    return True, user, db, first_message


@router.websocket("/ws/{device_id}")
async def websocket_device_endpoint(
    websocket: WebSocket,
    device_id: str
):
    """WebSocket endpoint for device (firmware) communication.
    
    Clients connect here to send commands to a device.
    The device_id is provided in URL path.
    The api_token is provided in Authorization header.
    
    URL format:
    /ws/{device_id}
    
    Authentication:
    - device_id in URL path identifies which device
    - Authorization header (Bearer {api_token}) authenticates the user
    - Server verifies user owns the device
    
    Device Token Usage:
    - device_token from database is used only for packet decryption
    - Never transmitted over the wire (kept server-side only)
    
    Protocol flow:
    1. Client connects to /ws/{device_id} with Authorization header
    2. Server validates api_token and checks device ownership
    3. Server sends welcome message
    4. Client sends encrypted packet with device_token in payload
    5. Server decrypts using device.device_token
    6. Server relays command to connected device (via separate connection)
    7. Device sends encrypted response back
    8. Server encrypts response using device.device_token
    9. Server relays response back to client
    
    Args:
        websocket: The WebSocket connection.
        device_id: Device identifier from URL path.
    """
    # Extract API token from Authorization header
    auth_header = websocket.headers.get("authorization", "")
    api_token = None
    
    if auth_header.lower().startswith("bearer "):
        api_token = auth_header[7:]  # Remove "Bearer " prefix
    
    if not api_token:
        await websocket.accept()
        await websocket.send_json({
            "status": "error",
            "error": "AUTH_REQUIRED",
            "message": "Authorization header with Bearer token is required"
        })
        await websocket.close(code=1008, reason="Missing Authorization header")
        return
    
    # Authenticate user and verify device ownership
    success, user, device, db = await _authenticate_websocket_device(
        websocket, device_id, api_token
    )
    
    if not success:
        return
    
    # Update device last_seen on connect
    device.last_seen = datetime.now().astimezone()
    db.commit()
    
    # Register in relay for command delivery
    await relay.connect(websocket, device_id, already_accepted=True)
    logger.info(f"[WSS] Device {device_id} connected for user {user.username}")
    
    try:
        await websocket.send_json({
            "type": "welcome",
            "status": "connected",
            "device_id": device_id,
            "protocol_version": "1.0",
            "message": "WebSocket connection established"
        })
        
        logger.info(f"[WSS] Welcome sent to {device_id}")
        
        # Keep connection alive - listen for messages from device
        # Device can send responses at any time
        while True:
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=None  # No timeout - device can be idle
                )
            except asyncio.TimeoutError:
                # This won't happen with timeout=None, but handles gracefully
                logger.warning(f"[WSS] Timeout waiting for data from {device_id}")
                continue
            except Exception as e:
                # Connection closed or other error
                logger.debug(f"[WSS] Device {device_id} connection error: {e}")
                break
            
            try:
                message_data = json.loads(raw_data)
            except json.JSONDecodeError:
                logger.warning(f"[WSS] Invalid JSON from device {device_id}")
                await websocket.send_json({
                    "status": "error",
                    "error": "INVALID_JSON",
                    "message": "Failed to parse JSON"
                })
                continue
            
            # Check for required fields (encrypted packet)
            required_fields = ["device_id", "payload", "signature", "version"]
            missing = [f for f in required_fields if f not in message_data]
            if missing:
                logger.warning(f"[WSS] Invalid packet from device {device_id}, missing: {missing}")
                await websocket.send_json({
                    "status": "error",
                    "error": "INVALID_PACKET",
                    "message": f"Missing fields: {missing}"
                })
                continue
            
            if message_data.get("version") != "1.0":
                logger.warning(f"[WSS] Unsupported version from device {device_id}")
                await websocket.send_json({
                    "status": "error",
                    "error": "UNSUPPORTED_VERSION",
                    "message": "Protocol version must be 1.0"
                })
                continue
            
            # Update device last_seen and request_counter
            target_device_id = message_data.get("device_id")
            device_record = db.query(Device).filter(Device.device_id == target_device_id).first()
            if device_record:
                device_record.last_seen = datetime.now().astimezone()
                if message_data.get("request_counter") is not None:
                    device_record.last_request_counter = message_data.get("request_counter")
                db.commit()
                logger.debug(f"[WSS] Device {target_device_id} last_seen updated")
            
            # This is a RESPONSE from device (since device is sending it)
            # Forward to the client that's waiting
            outer_packet = {
                "device_id": target_device_id,
                "payload": message_data.get("payload"),
                "signature": message_data.get("signature"),
                "request_counter": message_data.get("request_counter"),
                "version": "1.0"
            }
            
            # Try to forward to waiting client
            forwarded = await relay.push_response(device_id, outer_packet)
            
            if forwarded:
                logger.info(f"[WSS] Device {device_id} response forwarded to client")
            else:
                # No client waiting - store in DB for HTTP polling
                msg = Message(
                    device_id=target_device_id,
                    device_token=device.device_token if device else None,
                    message_type="response",
                    message_data=message_data.get("payload", ""),
                    signature=message_data.get("signature", ""),
                    direction="to_client"
                )
                db.add(msg)
                db.commit()
                logger.info(f"[WSS] Device {device_id} response queued for HTTP")
    
    except WebSocketDisconnect:
        logger.info(f"[WSS] Device disconnected: {device_id}")
    except Exception as e:
        logger.error(f"[WSS] Error for device {device_id}: {e}")
    finally:
        await relay.disconnect(device_id)


@router.websocket("/ws/client/{client_id}")
async def websocket_client_endpoint(
    websocket: WebSocket,
    client_id: str
):
    """WebSocket endpoint for CLI/application clients.
    
    Clients connect here to send commands to devices.
    The server tracks which client is waiting for which device response.
    
    Authentication:
    After connecting, client must send auth message:
    {"type": "auth", "token": "<api_token>"}
    
    Protocol flow:
    1. Client connects to /ws/client/{client_id}
    2. Client sends auth message with API token
    3. Server validates and sends welcome message
    4. Client sends command packet with target device_id
    5. Server relays to device (if online) or queues
    6. Server sends ACK to client
    7. When device responds, server forwards to client
    
    Args:
        websocket: The WebSocket connection.
        client_id: Unique client identifier.
    """
    success, user, db, first_message = await _authenticate_websocket(websocket)
    
    if not success:
        return
    
    connection_id = f"client_{client_id}"
    await relay.connect(websocket, connection_id)
    logger.info(f"[WSS] Client connected: {client_id} user={user.username}")
    
    try:
        await websocket.send_json({
            "type": "welcome",
            "status": "connected",
            "client_id": client_id,
            "protocol_version": "1.0",
            "message": "Client WebSocket connection established"
        })
        
        # Process first message if it was received during auth (legacy client)
        pending_message = first_message
        
        while True:
            if pending_message:
                message_data = pending_message
                pending_message = None
            else:
                raw_data = await websocket.receive_text()
                
                try:
                    message_data = json.loads(raw_data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "status": "error",
                        "error": "INVALID_JSON"
                    })
                    continue
            
            required_fields = ["device_id", "payload", "signature", "version"]
            missing = [f for f in required_fields if f not in message_data]
            if missing:
                await websocket.send_json({
                    "status": "error",
                    "error": "INVALID_PACKET",
                    "message": f"Missing: {missing}"
                })
                continue
            
            if message_data.get("version") != "1.0":
                await websocket.send_json({
                    "status": "error",
                    "error": "UNSUPPORTED_VERSION"
                })
                continue
            
            target_device_id = message_data.get("device_id")
            
            # Update device last_seen
            device = db.query(Device).filter(Device.device_id == target_device_id).first()
            if device:
                device.last_seen = datetime.now().astimezone()
                db.commit()
            
            # Build command packet to send to device
            outer_packet = {
                "device_id": target_device_id,
                "payload": message_data.get("payload"),
                "signature": message_data.get("signature"),
                "version": "1.0"
            }
            
            # Push to device, tracking that this client wants the response
            delivered = await relay.push(target_device_id, outer_packet, sender_id=connection_id)
            
            if not delivered:
                # Device offline - store command in DB
                msg = Message(
                    device_id=target_device_id,
                    device_token=device.device_token if device else None,
                    message_type="command",
                    message_data=message_data.get("payload", ""),
                    signature=message_data.get("signature", ""),
                    direction="to_device"
                )
                db.add(msg)
                db.commit()
            
            # Send ACK to client
            await websocket.send_json({
                "status": "success",
                "device_id": target_device_id,
                "delivered": delivered,
                "queued": not delivered,
                "message": "Delivered to device" if delivered else "Device offline, queued"
            })
            
            logger.debug(f"[WSS] Client {client_id} -> {target_device_id} delivered={delivered}")
    
    except WebSocketDisconnect:
        logger.info(f"[WSS] Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"[WSS] Client error {client_id}: {e}")
    finally:
        await relay.disconnect(connection_id)