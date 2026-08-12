-- Roommate Reviewer App — CS3200 Phase 2 Schema --
DROP DATABASE IF EXISTS roommate_app; CREATE DATABASE roommate_app; USE roommate_app;

DROP TABLE IF EXISTS Dorms;
CREATE TABLE Dorms (
    DormID    INT AUTO_INCREMENT PRIMARY KEY,
    Dorm_Name VARCHAR(100) NOT NULL
);

DROP TABLE IF EXISTS System_Admin;
CREATE TABLE System_Admin (
    AdminID 	INT AUTO_INCREMENT PRIMARY KEY,
    Email   	VARCHAR(255) NOT NULL UNIQUE,
    First_Name  VARCHAR(50)  NOT NULL,
    Last_Name   VARCHAR(50)  NOT NULL
);

DROP TABLE IF EXISTS Rooms;
CREATE TABLE Rooms (
    RoomID  	INT AUTO_INCREMENT PRIMARY KEY,
    DormID  	INT NOT NULL,
    Room_Number VARCHAR(10) NOT NULL,
    RA      	VARCHAR(100),
    FOREIGN KEY (DormID) REFERENCES Dorms(DormID)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (DormID, Room_Number)
);

DROP TABLE IF EXISTS RAs;
CREATE TABLE RAs (
    UserID   	INT AUTO_INCREMENT PRIMARY KEY,
    First_Name   VARCHAR(50)  NOT NULL,
    Last_Name	VARCHAR(50)  NOT NULL,
    Email    	VARCHAR(255) NOT NULL UNIQUE,
    RA_ID    	INT,
    Settled_Reqs INT NOT NULL DEFAULT 0,
    Settled_Reps INT NOT NULL DEFAULT 0,
    Year     	INT
);

DROP TABLE IF EXISTS Users;
CREATE TABLE Users (
    UserID      	INT AUTO_INCREMENT PRIMARY KEY,
    First_Name  	VARCHAR(50)  NOT NULL,
    Last_Name   	VARCHAR(50)  NOT NULL,
    Email       	VARCHAR(255) NOT NULL UNIQUE,
    RA          	INT,
    RoomID      	INT,
    TasksCompleted  INT NOT NULL DEFAULT 0,
    TasksMissed 	INT NOT NULL DEFAULT 0,
    FOREIGN KEY (RA) 	REFERENCES RAs(UserID)   ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID) ON DELETE SET NULL ON UPDATE CASCADE
);

DROP TABLE IF EXISTS Requests;
CREATE TABLE Requests (
    Request_ID   	INT AUTO_INCREMENT PRIMARY KEY,
    Status       	ENUM('open','in_progress','resolved','rejected') NOT NULL DEFAULT 'open',
    Reason       	TEXT,
    Request_Type 	VARCHAR(50) NOT NULL,
    Created_At   	DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Proposed_Due_Date DATE,
    Task_ID      	INT,
    -- Who filed the request. Without this a request can only be traced to a person
    -- through Task_ID, which is NULL for expunction requests -- so those would be
    -- unattributable. Users is created above, so the FK can be declared inline.
    Requested_By_UserID INT,
    FOREIGN KEY (Requested_By_UserID) REFERENCES Users(UserID)
        ON DELETE SET NULL ON UPDATE CASCADE
);

DROP TABLE IF EXISTS Tasks;
CREATE TABLE Tasks (
    Task_ID    	INT AUTO_INCREMENT PRIMARY KEY,
    Task_Name  	VARCHAR(150) NOT NULL,
    Created_At 	DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_date   	DATE,
    status     	ENUM('todo','in_progress','done','missed') NOT NULL DEFAULT 'todo',
    Created_UserID INT NOT NULL,
    Assigned_UserID INT,
    Request_ID 	INT,
    FOREIGN KEY (Created_UserID)  REFERENCES Users(UserID) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (Assigned_UserID) REFERENCES Users(UserID) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (Request_ID)  	REFERENCES Requests(Request_ID) ON DELETE SET NULL ON UPDATE CASCADE
);

ALTER TABLE Requests
    ADD FOREIGN KEY (Task_ID) REFERENCES Tasks(Task_ID)
        ON DELETE SET NULL ON UPDATE CASCADE;

DROP TABLE IF EXISTS RA_Intervention;
CREATE TABLE RA_Intervention (
    RequestID   INT AUTO_INCREMENT PRIMARY KEY,
    Description TEXT,
    Status  	ENUM('pending','active','closed') NOT NULL DEFAULT 'pending',
    UserID  	INT NOT NULL,
    RA      	INT,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE  ON UPDATE CASCADE,
    FOREIGN KEY (RA) 	REFERENCES RAs(UserID)   ON DELETE SET NULL ON UPDATE CASCADE
);

DROP TABLE IF EXISTS Room_Reports;
CREATE TABLE Room_Reports (
    ReportID  	INT AUTO_INCREMENT PRIMARY KEY,
    Time_Reported DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Status    	ENUM('open','reviewed','closed') NOT NULL DEFAULT 'open',
    TaskID    	INT,
    UserID    	INT NOT NULL,
    RequestID 	INT,
    Description TEXT,
    FOREIGN KEY (TaskID)	REFERENCES Tasks(Task_ID)    	ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (UserID)	REFERENCES Users(UserID)     	ON DELETE CASCADE  ON UPDATE CASCADE,
    FOREIGN KEY (RequestID) REFERENCES Requests(Request_ID)  ON DELETE SET NULL ON UPDATE CASCADE
);

DROP TABLE IF EXISTS UserAway;
CREATE TABLE UserAway (
    AwayID 	INT AUTO_INCREMENT PRIMARY KEY,
    UserID 	INT NOT NULL,
    Start_Date DATE NOT NULL,
    End_Date   DATE NOT NULL,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (End_Date >= Start_Date)
);

DROP TABLE IF EXISTS Logs;
CREATE TABLE Logs (
    Log_Id 	INT AUTO_INCREMENT PRIMARY KEY,
    UserId 	INT NOT NULL,
    Timestamp  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Action 	VARCHAR(255) NOT NULL,
    ReviewerID INT,
    FOREIGN KEY (UserId) 	REFERENCES Users(UserID)      	ON DELETE CASCADE  ON UPDATE CASCADE,
    FOREIGN KEY (ReviewerID) REFERENCES System_Admin(AdminID)  ON DELETE SET NULL ON UPDATE CASCADE
);

DROP TABLE IF EXISTS Rules;
CREATE TABLE Rules (
    RuleID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT,
    Descr  TEXT NOT NULL,
    RA_ID  INT,
    RoomID INT,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (RA_ID)  REFERENCES RAs(UserID)   ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID) ON DELETE SET NULL ON UPDATE CASCADE
);



-- SAMPLE DATA --
INSERT INTO Dorms (DormID, Dorm_Name) VALUES
(1, 'North Hall'),
(2, 'South Hall'),
(3, 'West Village');

INSERT INTO System_Admin (AdminID, Email, First_Name, Last_Name) VALUES
(1, 'admin.reynolds@northeastern.edu', 'Sam',   'Reynolds'),
(2, 'admin.cho@northeastern.edu',      'Jamie', 'Cho');

INSERT INTO Rooms (RoomID, DormID, Room_Number, RA) VALUES
(1, 1, '101', 'Carol Diaz'),
(2, 1, '102', 'Carol Diaz'),
(3, 2, '201', 'Dave Kim'),
(4, 3, '305', 'Priya Raman');

INSERT INTO RAs (UserID, First_Name, Last_Name, Email, RA_ID, Settled_Reqs, Settled_Reps, Year) VALUES
(1, 'Carol', 'Diaz',   'carol.diaz@northeastern.edu',   101, 12, 5, 2026),
(2, 'Dave',  'Kim',    'dave.kim@northeastern.edu',     102,  9, 3, 2027),
(3, 'Priya', 'Raman',  'priya.raman@northeastern.edu',  103,  4, 1, 2026);

INSERT INTO Users (UserID, First_Name, Last_Name, Email, RA, RoomID, TasksCompleted, TasksMissed) VALUES
(1, 'Alice', 'Nguyen', 'alice.nguyen@northeastern.edu', 1, 1, 4, 0),
(2, 'Bob',   'Smith',  'bob.smith@northeastern.edu',    1, 2, 2, 1),
(3, 'Erin',  'Walsh',  'erin.walsh@northeastern.edu',   2, 3, 1, 2),
(4, 'Frank', 'Osei',   'frank.osei@northeastern.edu',   2, 3, 0, 3),
(5, 'Grace', 'Lin',    'grace.lin@northeastern.edu',    3, 4, 6, 0);

INSERT INTO Requests (Request_ID, Status, Reason, Request_Type, Created_At, Proposed_Due_Date, Task_ID, Requested_By_UserID) VALUES
(1, 'resolved',    'Bathroom sink has been leaking since Friday.',      'maintenance', '2026-08-01 08:45:00', '2026-08-15', NULL, 2),
(2, 'open',        'Hallway lightbulb outside 102 is burned out.',      'maintenance', '2026-08-02 14:10:00', '2026-08-20', NULL, 1),
(3, 'in_progress', 'Requesting a chore swap during midterm exam week.', 'chore_swap',  '2026-08-03 07:55:00', '2026-08-25', NULL, 4),
(4, 'rejected',    'Asked to be reassigned to a single room.',          'room_change', '2026-08-04 19:20:00', '2026-09-01', NULL, 3);

INSERT INTO Tasks (Task_ID, Task_Name, Created_At, due_date, status, Created_UserID, Assigned_UserID, Request_ID) VALUES
(1, 'Clean shared bathroom',      '2026-08-01 09:00:00', '2026-08-15', 'done',        1, 2, 1),
(2, 'Replace hallway lightbulb',  '2026-08-02 14:30:00', '2026-08-20', 'todo',        2, 1, 2),
(3, 'Take out recycling',         '2026-08-03 08:15:00', '2026-08-25', 'in_progress', 3, 4, 3),
(4, 'Vacuum the common room',     '2026-08-04 17:45:00', '2026-08-18', 'missed',      5, 5, NULL),
-- Frank Osei (UserID 4) carries TasksMissed = 3 but only one task was assigned to him,
-- so the counter matched nothing. These three missed tasks make it add up and give the
-- accountability dashboard (story 3.5) and strike expunction (story 3.6) real rows to
-- work with -- a strike is an open report about a task assigned to you.
(5, 'Take out trash',             '2026-07-18 09:00:00', '2026-07-20', 'missed',      3, 4, NULL),
(6, 'Wipe down counters',         '2026-06-13 18:30:00', '2026-06-15', 'missed',      1, 4, NULL),
(7, 'Clean the microwave',        '2026-07-02 12:00:00', '2026-07-04', 'missed',      3, 4, NULL);

UPDATE Requests SET Task_ID = 1 WHERE Request_ID = 1;
UPDATE Requests SET Task_ID = 2 WHERE Request_ID = 2;
UPDATE Requests SET Task_ID = 3 WHERE Request_ID = 3;

-- Requests using Persona 3 (Ronny RuleBreaker) vocabulary: extension / dispute /
-- expunction / swap. Inserted after Tasks so Task_ID can be set directly rather
-- than backfilled. Frank Osei (UserID 4, 0 completed / 3 missed) is the Ronny
-- stand-in; Erin Walsh (3) shares RoomID 3 with him.
-- Requests 7, 8 and 10 carry Task_ID = NULL: a dispute challenges a report and an
-- expunction challenges a strike, so neither points at a task. Those rows are
-- traceable to a person only through Requested_By_UserID.
INSERT INTO Requests (Request_ID, Status, Reason, Request_Type, Created_At, Proposed_Due_Date, Task_ID, Requested_By_UserID) VALUES
(5,  'open',     'Work shift ran long -- requesting two extra days on recycling.',   'extension',  '2026-08-05 21:40:00', '2026-08-28', 3,    4),
(6,  'open',     'Offering recycling in exchange for a later common-room chore.',    'swap',       '2026-08-06 08:05:00', NULL,         3,    4),
(7,  'open',     'Disputing report #3: I was away that week, photo evidence in-app.', 'dispute',   '2026-08-06 19:15:00', NULL,         NULL, 4),
(8,  'open',     'Requesting the June strike be voided -- 11 tasks on time since.',  'expunction', '2026-08-07 12:30:00', NULL,         NULL, 4),
(9,  'resolved', 'Exam week conflict; roommates approved the later date.',           'extension',  '2026-08-02 16:20:00', '2026-08-21', 4,    5),
(10, 'rejected', 'Disputed the vacuum mark, roommates voted it down.',               'dispute',    '2026-08-04 09:50:00', NULL,         NULL, 3);

INSERT INTO RA_Intervention (RequestID, Description, Status, UserID, RA) VALUES
(1, 'Three missed chores in a row; weekly check-in scheduled.', 'active',  4, 2),
(2, 'Mediated a noise complaint between roommates in 201.',     'closed',  3, 2),
(3, 'Follow up on unresolved room change request.',             'pending', 5, 3);

INSERT INTO Room_Reports (ReportID, Time_Reported, Status, TaskID, UserID, RequestID, Description) VALUES
(1, '2026-08-01 10:05:00', 'closed',   1, 1,    1, 'Bathroom hasnt been cleaned yet'),
(2, '2026-08-02 15:00:00', 'open',     2, 2,    2, 'Hallway is still super dark'),
(3, '2026-08-04 18:00:00', 'reviewed', 4, 5, NULL, 'Common room floor is super dirty'),
-- Reports against Frank Osei (UserID 4). Note UserID here is the roommate who FILED
-- the report; the person blamed is reached through TaskID -> Tasks.Assigned_UserID.
-- Reports 4 and 5 are open, so Frank has two live strikes; report 5 is the old June one
-- that expunction request 8 is asking to void, linked through RequestID.
(4, '2026-07-21 09:15:00', 'open',     5, 3,    NULL, 'Trash not taken out yet'),
(5, '2026-06-16 20:30:00', 'open',     6, 1,    8, 'Counters are dirty still'),
(6, '2026-07-05 08:40:00', 'closed',   7, 3,    NULL, 'Microwave is still dirty');

INSERT INTO UserAway (AwayID, UserID, Start_Date, End_Date) VALUES
(1, 1, '2026-07-01', '2026-07-10'),
(2, 3, '2026-08-05', '2026-08-09'),
(3, 5, '2026-08-20', '2026-08-27');

INSERT INTO Logs (Log_Id, UserId, `Timestamp`, `Action`, ReviewerID) VALUES
(1, 1, '2026-08-01 09:01:00', 'Submitted maintenance request #1',   NULL),
(2, 2, '2026-08-01 11:30:00', 'Marked task #1 as done',                1),
(3, 4, '2026-08-03 22:15:00', 'Flagged for missed chore assignment',   2);

INSERT INTO Rules (RuleID, UserID, Descr, RA_ID, RoomID) VALUES
(1, 1, 'Quiet hours begin at 10:00 PM on weeknights.',              1, 1),
(2, 3, 'No overnight guests without roommate approval.',            2, 3),
(3, 5, 'Dishes must be washed the same day they are used.',         3, 4);
