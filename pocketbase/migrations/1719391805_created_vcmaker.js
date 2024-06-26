/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const collection = new Collection({
    "id": "xbis2vr63respq6",
    "created": "2024-06-26 08:50:05.456Z",
    "updated": "2024-06-26 08:50:05.456Z",
    "name": "vcmaker",
    "type": "base",
    "system": false,
    "schema": [
      {
        "system": false,
        "id": "w1u5vyhq",
        "name": "channelID",
        "type": "number",
        "required": true,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "noDecimal": true
        }
      },
      {
        "system": false,
        "id": "5uqjrk6w",
        "name": "type",
        "type": "select",
        "required": true,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSelect": 1,
          "values": [
            "TEMPORARY",
            "PERMANENT"
          ]
        }
      }
    ],
    "indexes": [
      "CREATE UNIQUE INDEX `idx_FsEfgLF` ON `vcmaker` (`channelID`)"
    ],
    "listRule": null,
    "viewRule": null,
    "createRule": null,
    "updateRule": null,
    "deleteRule": null,
    "options": {}
  });

  return Dao(db).saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("xbis2vr63respq6");

  return dao.deleteCollection(collection);
})
