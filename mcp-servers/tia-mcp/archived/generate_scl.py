import json, os

SCL_CODE = '''FUNCTION_BLOCK "MaterialCartControl"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'

VAR_INPUT
    bStart : Bool;
    bStop : Bool;
    bReset : Bool;
    bEmergencyStop : Bool;
    bForwardLimit : Bool;
    bReverseLimit : Bool;
    bOverload : Bool;
    bManualMode : Bool;
    bManualForward : Bool;
    bManualReverse : Bool;
    iCycleSetpoint : Int;
    tiUnloadTime : Time := T#5S;
    tiLoadTime : Time := T#3S;
END_VAR

VAR_OUTPUT
    bForwardOut : Bool;
    bReverseOut : Bool;
    bRunning : Bool;
    bFault : Bool;
    iFaultCode : Int;
    iCycleCount : Int;
    iStateDisplay : Int;
    bAtForwardEnd : Bool;
    bAtReverseEnd : Bool;
END_VAR

VAR
    iState : Int := 0;
    tStartTimer : Time;
    bHoldStop : Bool;
    bFaultLatch : Bool;
END_VAR

BEGIN
    bForwardOut := FALSE;
    bReverseOut := FALSE;
    bRunning := FALSE;
    bFault := FALSE;
    bAtForwardEnd := FALSE;
    bAtReverseEnd := FALSE;
    iStateDisplay := iState;

    IF NOT bEmergencyStop THEN
        bForwardOut := FALSE; bReverseOut := FALSE; bRunning := FALSE;
        bFault := TRUE; bFaultLatch := TRUE; iFaultCode := 1; iState := 5;
        RETURN;
    END_IF;

    IF NOT bOverload THEN
        bForwardOut := FALSE; bReverseOut := FALSE; bRunning := FALSE;
        bFault := TRUE; bFaultLatch := TRUE; iFaultCode := 2; iState := 5;
        RETURN;
    END_IF;

    IF bManualMode THEN
        IF bManualForward AND NOT bManualReverse THEN bForwardOut := TRUE; bReverseOut := FALSE;
        ELSIF bManualReverse AND NOT bManualForward THEN bForwardOut := FALSE; bReverseOut := TRUE;
        ELSE bForwardOut := FALSE; bReverseOut := FALSE; END_IF;
        RETURN;
    END_IF;

    IF bFaultLatch AND bReset THEN
        bFaultLatch := FALSE; bHoldStop := FALSE; iFaultCode := 0; iState := 0;
    END_IF;
    IF bFaultLatch THEN bForwardOut := FALSE; bReverseOut := FALSE; bFault := TRUE; RETURN; END_IF;

    CASE iState OF
        0:
            IF bStart THEN bHoldStop := FALSE; iCycleCount := 0; iState := 1; END_IF;
        1:
            bForwardOut := TRUE; bRunning := TRUE;
            IF bForwardLimit THEN bForwardOut := FALSE; tStartTimer := T#0S; iState := 2;
            ELSIF bReverseLimit THEN bForwardOut := FALSE; iFaultCode := 4; bFaultLatch := TRUE; iState := 5; END_IF;
        2:
            bAtForwardEnd := TRUE; bRunning := TRUE;
            tStartTimer := tStartTimer + T#1S;
            IF tStartTimer >= tiUnloadTime THEN bAtForwardEnd := FALSE; tStartTimer := T#0S; iState := 3; END_IF;
        3:
            bReverseOut := TRUE; bRunning := TRUE;
            IF bReverseLimit THEN bReverseOut := FALSE; tStartTimer := T#0S; iState := 4;
            ELSIF bForwardLimit THEN bReverseOut := FALSE; iFaultCode := 4; bFaultLatch := TRUE; iState := 5; END_IF;
        4:
            bAtReverseEnd := TRUE; bRunning := TRUE;
            tStartTimer := tStartTimer + T#1S;
            IF tStartTimer >= tiLoadTime THEN
                bAtReverseEnd := FALSE; iCycleCount := iCycleCount + 1; tStartTimer := T#0S;
                IF bHoldStop THEN iState := 0;
                ELSIF iCycleSetpoint > 0 AND iCycleCount >= iCycleSetpoint THEN iState := 0;
                ELSE iState := 1; END_IF;
            END_IF;
        5:
            bFault := TRUE;
            IF bReset THEN bFaultLatch := FALSE; iFaultCode := 0; iState := 0; END_IF;
    END_CASE;

    IF bStop AND iState >= 1 AND iState <= 4 THEN bHoldStop := TRUE; END_IF;
END_FUNCTION_BLOCK
'''

def main():
    scl_dir = os.path.join(os.environ.get("TEMP", "/tmp"), "tia-scl")
    os.makedirs(scl_dir, exist_ok=True)
    scl_file = os.path.join(scl_dir, "MaterialCartControl.scl")
    with open(scl_file, "w", encoding="utf-8") as f:
        f.write(SCL_CODE)
    print(json.dumps({"status":"ok","data":{"scl_code":SCL_CODE,"block_name":"MaterialCartControl","file_path":scl_file}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
