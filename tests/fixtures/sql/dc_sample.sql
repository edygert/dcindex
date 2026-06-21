-- Synthetic Outel-style DEF CON dump for tests. Mixes table families from several years on purpose
-- to exercise the tolerant mapper. Reproduces real quirks: no INSERT column list, literal wrapping
-- single-quotes around values, backslash escapes (\n), doubled '' quotes, continuation rows, and
-- URLs embedded as <a href> inside HTML description columns.

CREATE TABLE `events` (
  `day` varchar(16) NOT NULL,
  `hour` varchar(2) NOT NULL,
  `starttime` varchar(6) NOT NULL,
  `endtime` varchar(6) NOT NULL,
  `continuation` char(1) NOT NULL,
  `village` varchar(90) NOT NULL,
  `track` varchar(90) NOT NULL,
  `title` varchar(512) NOT NULL,
  `speaker` varchar(256) NOT NULL,
  `hash` varchar(64) NOT NULL,
  `desc` text NOT NULL,
  `modflag` tinyint(4) DEFAULT NULL,
  `autoincre` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`autoincre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `events` VALUES
('3_Saturday','14','14:30','15:30','N','OS','Track 1 - Main Stage','\'Breaking Kernels\'','\'Alice Lee\'','H1','\'<font><strong>Title:</strong></font> Breaking Kernels<br>\nDescription:<br>\nUses <a href="https://github.com/acme/kernel-tool">the tool</a>; discuss on the <a href="https://forum.defcon.org/node/1001">forum</a>; slides <a href="https://media.example.org/slides.pdf">here</a>.\'',NULL,1),
('3_Saturday','15','15:00','16:00','Y','OS','Track 1 - Main Stage','\'Breaking Kernels\'','\'Alice Lee\'','H1','\'continuation row, must be skipped\'',NULL,2),
('4_Sunday','10','10:00','11:00','N','APP','Track 2 - Side Room','\'Web Workshop\'','\'Bob Roberts\'','H2','\'<p>Workshoppy talk. It''s great fun. Watch the <a href="https://youtu.be/abc123">video</a>.</p>\'',NULL,3);

CREATE TABLE `speakers` (
  `speaker_sort` varchar(128) NOT NULL,
  `speaker` varchar(128) NOT NULL,
  `hash` varchar(64) NOT NULL,
  `autoincre` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`autoincre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `speakers` VALUES
('\'Lee, Alice\'','\'Alice Lee\'','H1',10),
('\'Diaz, Carol\'','\'Carol Diaz\'','H1',11),
('\'Roberts, Bob\'','\'Bob Roberts\'','H2',12);

CREATE TABLE `demolabs` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `Name` varchar(200) NOT NULL,
  `ForumPage` varchar(60) NOT NULL,
  `ForumArticle` varchar(40) NOT NULL,
  `Webpage` varchar(60) NOT NULL,
  `Weblink` varchar(60) NOT NULL,
  `ImagePath` varchar(30) NOT NULL,
  `Descript` varchar(15000) NOT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `demolabs` VALUES
(5,'\'Cool Demo Lab - Dana Smith\'','https://forum.defcon.org/node/2001','','https://example.org/demo','https://github.com/acme/demo','img/x.png','\'<p>A neat demo. See <a href="https://github.com/acme/demo2">repo2</a>.</p>\'');

CREATE TABLE `villages` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `Name` varchar(45) NOT NULL,
  `HomePage` varchar(70) NOT NULL,
  `SchedulePage` varchar(90) NOT NULL,
  `DCForumPage` varchar(50) DEFAULT NULL,
  `VillageDesc` text NOT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `villages` VALUES
(7,'\'IoT Village\'','https://iotvillage.org','https://iotvillage.org/schedule','https://forum.defcon.org/node/3001','\'<p>Hack all the IoT. Grab the <a href="https://github.com/iot/tools">tools</a>.</p>\'');

CREATE TABLE `pages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `pagetype` varchar(40) NOT NULL,
  `description` text NOT NULL,
  `imageurl` varchar(120) NOT NULL,
  `imagename` varchar(60) NOT NULL,
  `forumpage` varchar(80) NOT NULL,
  `forumarticle` varchar(40) NOT NULL,
  `linkname` varchar(60) NOT NULL,
  `linkurl` varchar(120) NOT NULL,
  `orgas_id` int(11) NOT NULL,
  `location` varchar(100) NOT NULL,
  `sessiontimes` varchar(120) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `pages` VALUES
(9,'\'Lockpick Village\'','village','\'<p>Pick all the locks.</p>\'','','','https://forum.defcon.org/node/4001','','site','https://lockpickvillage.org',0,'\'Hall A\'','\'Fri 10:00-17:00\'');

CREATE TABLE `vendors` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(60) NOT NULL,
  `description` varchar(5000) NOT NULL,
  `linktitle` varchar(60) NOT NULL,
  `link` varchar(60) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `vendors` VALUES
(3,'\'Hacker Warehouse\'','\'Gear and gadgets.\'','site','https://hackerwarehouse.com');

CREATE TABLE `documents` (
  `title` varchar(120) NOT NULL,
  `content` text NOT NULL,
  `sortorder` int(11) NOT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `hash` varchar(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `documents` VALUES
('\'Code of Conduct\'','\'<p>Be excellent to each other.</p>\'',1,1,'DOC1');

CREATE TABLE `random_extra` (
  `id` int(11) NOT NULL,
  `val` varchar(20) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `random_extra` VALUES (1,'unknown');
